"""FastAPI 路由:说明书库 / 抽取明细 / 知识图谱 / 审核台 / 冲突检查 / 导出。"""
from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    Conflict, ContraindicationFact, Document, DosageFact, DrugEntity,
    InteractionFact, KnowledgeItem, Section,
)
from app.db.session import get_session
from app.extract.exporter import export_approved

router = APIRouter(prefix="/api")


class ReviewBody(BaseModel):
    status: str           # approved / rejected / pending
    note: str = ""
    reviewer: str = "药师"


class BatchReviewBody(BaseModel):
    ids: list[int]
    status: str
    note: str = ""
    reviewer: str = "药师"


# ---------- 说明书库 ----------

@router.get("/documents")
def list_documents(
    q: str = "", style: str = "", page: int = 1, size: int = 20,
    session: Session = Depends(get_session),
):
    stmt = select(Document)
    if q:
        like = f"%{q}%"
        stmt = stmt.where((Document.generic_name.like(like))
                          | (Document.doc_no.like(like))
                          | (Document.manufacturer.like(like)))
    if style:
        stmt = stmt.where(Document.style_family == style)
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = session.scalars(
        stmt.order_by(Document.doc_no).offset((page - 1) * size).limit(size)
    ).all()
    return {"total": total, "items": [_doc_brief(d, session) for d in rows]}


def _doc_brief(d: Document, session: Session) -> dict:
    item_count = session.scalar(
        select(func.count()).select_from(KnowledgeItem)
        .where(KnowledgeItem.document_id == d.id))
    return {
        "doc_no": d.doc_no, "title": d.title, "generic_name": d.generic_name,
        "manufacturer": d.manufacturer, "approval_no": d.approval_no,
        "file_type": d.file_type, "style_family": d.style_family,
        "item_count": item_count, "created_at": d.created_at,
    }


@router.get("/documents/{doc_no}")
def document_detail(doc_no: str, session: Session = Depends(get_session)):
    d = _get_doc(session, doc_no)
    sections = session.scalars(
        select(Section).where(Section.document_id == d.id)
        .order_by(Section.order_index)).all()
    return {
        "doc_no": d.doc_no, "title": d.title, "generic_name": d.generic_name,
        "manufacturer": d.manufacturer, "approval_no": d.approval_no,
        "file_type": d.file_type, "style_family": d.style_family,
        "full_text": d.full_text,
        "sections": [{"code": s.code, "raw_heading": s.raw_heading,
                      "text": s.text, "order_index": s.order_index} for s in sections],
    }


# ---------- 抽取明细 ----------

@router.get("/items")
def list_items(
    type: str = "", status: str = "", doc_no: str = "",
    page: int = 1, size: int = 20, session: Session = Depends(get_session),
):
    stmt = select(KnowledgeItem).options(
        selectinload(KnowledgeItem.interaction),
        selectinload(KnowledgeItem.dosage),
        selectinload(KnowledgeItem.contraindication),
    )
    if type:
        stmt = stmt.where(KnowledgeItem.item_type == type)
    if status:
        stmt = stmt.where(KnowledgeItem.review_status == status)
    if doc_no:
        doc = session.scalar(select(Document).where(Document.doc_no == doc_no))
        if not doc:
            raise HTTPException(404, "说明书不存在")
        stmt = stmt.where(KnowledgeItem.document_id == doc.id)
    total = session.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = session.scalars(
        stmt.order_by(KnowledgeItem.id).offset((page - 1) * size).limit(size)
    ).all()
    doc_nos = {d.id: d.doc_no for d in session.scalars(select(Document)).all()}
    return {"total": total, "items": [_item_dict(x, doc_nos.get(x.document_id))
                                      for x in rows]}


def _item_dict(x: KnowledgeItem, doc_no: str) -> dict:
    base = {
        "id": x.id, "doc_no": doc_no, "item_type": x.item_type,
        "section_code": x.section_code, "source_text": x.source_text,
        "source_start": x.source_start, "source_end": x.source_end,
        "confidence": x.confidence, "review_status": x.review_status,
        "reviewer": x.reviewer, "review_note": x.review_note,
        "reviewed_at": x.reviewed_at,
    }
    if x.interaction:
        f = x.interaction
        base["fact"] = {
            "drug_a": f.drug_a, "drug_b": f.drug_b, "pair_key": f.pair_key,
            "interaction_type": f.interaction_type, "severity": f.severity,
            "effect_desc": f.effect_desc,
            "mentioned_a": f.mentioned_a, "mentioned_b": f.mentioned_b,
        }
    elif x.dosage:
        f = x.dosage
        base["fact"] = {
            "population": f.population, "population_label": f.population_label,
            "dose_value": f.dose_value, "dose_min": f.dose_min,
            "dose_max": f.dose_max, "dose_unit": f.dose_unit,
            "frequency": f.frequency, "frequency_label": f.frequency_label,
            "route": f.route,
        }
    elif x.contraindication:
        f = x.contraindication
        base["fact"] = {"subject": f.subject, "category": f.category}
    return base


# ---------- 审核台 ----------

@router.post("/items/{item_id}/review")
def review_item(item_id: int, body: ReviewBody,
                session: Session = Depends(get_session)):
    if body.status not in ("approved", "rejected", "pending"):
        raise HTTPException(400, "非法审核状态")
    item = session.get(KnowledgeItem, item_id)
    if not item:
        raise HTTPException(404, "知识条目不存在")
    item.review_status = body.status
    item.review_note = body.note
    item.reviewer = body.reviewer
    import datetime as _dt
    item.reviewed_at = _dt.datetime.now().isoformat(timespec="seconds")
    session.commit()
    return {"ok": True, "id": item_id, "status": body.status}


@router.post("/review/batch")
def review_batch(body: BatchReviewBody,
                 session: Session = Depends(get_session)):
    import datetime as _dt
    now = _dt.datetime.now().isoformat(timespec="seconds")
    n = 0
    for iid in body.ids:
        item = session.get(KnowledgeItem, iid)
        if item:
            item.review_status = body.status
            item.review_note = body.note
            item.reviewer = body.reviewer
            item.reviewed_at = now
            n += 1
    session.commit()
    return {"ok": True, "updated": n}


@router.get("/review/stats")
def review_stats(session: Session = Depends(get_session)):
    rows = session.execute(
        select(KnowledgeItem.item_type, KnowledgeItem.review_status,
               func.count()).group_by(KnowledgeItem.item_type,
                                      KnowledgeItem.review_status)
    ).all()
    stats: dict[str, dict[str, int]] = defaultdict(dict)
    for item_type, status, cnt in rows:
        stats[item_type][status] = cnt
    return {"stats": dict(stats)}


# ---------- 知识图谱 ----------

@router.get("/graph")
def knowledge_graph(severity: str = "", session: Session = Depends(get_session)):
    """药物节点 + 相互作用边(去重),供前端 SVG 力导向图渲染。"""
    stmt = select(InteractionFact).join(
        KnowledgeItem, InteractionFact.item_id == KnowledgeItem.id)
    if severity:
        stmt = stmt.where(InteractionFact.severity == severity)
    facts = session.scalars(stmt).all()
    nodes: dict[str, dict] = {}
    edges: dict[str, dict] = {}
    for f in facts:
        nodes.setdefault(f.drug_a, {"id": f.drug_a, "label": f.drug_a, "degree": 0})
        nodes.setdefault(f.drug_b, {"id": f.drug_b, "label": f.drug_b, "degree": 0})
        nodes[f.drug_a]["degree"] += 1
        nodes[f.drug_b]["degree"] += 1
        e = edges.setdefault(f.pair_key, {
            "source": f.drug_a, "target": f.drug_b,
            "severity": f.severity, "interaction_type": f.interaction_type,
            "count": 0,
        })
        e["count"] += 1
    return {"nodes": sorted(nodes.values(), key=lambda x: -x["degree"]),
            "edges": list(edges.values())}


# ---------- 冲突检查 ----------

@router.get("/conflicts")
def list_conflicts(resolved: bool | None = None,
                   session: Session = Depends(get_session)):
    stmt = select(Conflict)
    if resolved is not None:
        stmt = stmt.where(Conflict.resolved == resolved)
    rows = session.scalars(stmt.order_by(Conflict.id)).all()
    return {"total": len(rows), "items": [{
        "id": c.id, "pair_key": c.pair_key, "drug_a": c.drug_a, "drug_b": c.drug_b,
        "conflict_type": c.conflict_type, "doc_no_1": c.doc_no_1,
        "doc_no_2": c.doc_no_2, "detail": c.detail, "resolved": c.resolved,
        "item_id_1": c.item_id_1, "item_id_2": c.item_id_2,
    } for c in rows]}


@router.post("/conflicts/{conflict_id}/resolve")
def resolve_conflict(conflict_id: int, session: Session = Depends(get_session)):
    c = session.get(Conflict, conflict_id)
    if not c:
        raise HTTPException(404, "冲突不存在")
    c.resolved = True
    session.commit()
    return {"ok": True, "id": conflict_id}


# ---------- 药名词典 ----------

@router.get("/drugs")
def list_drugs(session: Session = Depends(get_session)):
    rows = session.scalars(select(DrugEntity).order_by(DrugEntity.generic_name)).all()
    return {"items": [{
        "generic_name": d.generic_name, "trade_names": d.trade_names,
        "aliases": d.aliases, "atc_category": d.atc_category,
    } for d in rows]}


# ---------- 导出 ----------

@router.post("/export")
def export_kb(session: Session = Depends(get_session)):
    try:
        return export_approved(session)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


def _get_doc(session: Session, doc_no: str) -> Document:
    d = session.scalar(select(Document).where(Document.doc_no == doc_no))
    if not d:
        raise HTTPException(404, "说明书不存在")
    return d
