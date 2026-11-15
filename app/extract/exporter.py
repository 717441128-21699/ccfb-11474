"""审方系统知识导出:仅导出审核通过的知识条目,带版本号与校验和。

导出 JSON 结构:
{
  "version": "YYYYMMDD-HHMMSS",
  "generated_at": ISO 时间,
  "checksum": sha256,
  "stats": {...},
  "interactions": [...], "dosages": [...], "contraindications": [...]
}
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import EXPORT_DIR
from app.db.models import (
    ContraindicationFact, Document, DosageFact, ExportLog,
    InteractionFact, KnowledgeItem,
)
from app.normalize.canonical import canonical


def _doc_no_of(session: Session, doc_id: int) -> str:
    doc = session.get(Document, doc_id)
    return doc.doc_no if doc else ""


def export_approved(session: Session) -> dict:
    approved_ids = session.scalars(
        select(KnowledgeItem.id).where(KnowledgeItem.review_status == "approved")
    ).all()
    if not approved_ids:
        raise ValueError("没有审核通过的知识条目可导出")

    interactions, dosages, contraindications = [], [], []
    for f in session.scalars(
        select(InteractionFact).where(InteractionFact.item_id.in_(approved_ids))
    ).all():
        item = session.get(KnowledgeItem, f.item_id)
        interactions.append({
            "drug_a": canonical(f.drug_a),
            "drug_b": canonical(f.drug_b),
            "pair_key": f.pair_key,
            "interaction_type": f.interaction_type,
            "severity": f.severity,
            "effect_desc": f.effect_desc,
            "source": {
                "doc_no": _doc_no_of(session, item.document_id),
                "section": item.section_code,
                "quote": item.source_text,
                "offset": [item.source_start, item.source_end],
            },
        })
    for f in session.scalars(
        select(DosageFact).where(DosageFact.item_id.in_(approved_ids))
    ).all():
        item = session.get(KnowledgeItem, f.item_id)
        dosages.append({
            "drug": canonical(session.get(Document, item.document_id).generic_name),
            "population": f.population,
            "population_label": f.population_label,
            "dose_value": f.dose_value,
            "dose_min": f.dose_min,
            "dose_max": f.dose_max,
            "dose_unit": f.dose_unit,
            "frequency": f.frequency,
            "frequency_label": f.frequency_label,
            "route": f.route,
            "source": {
                "doc_no": _doc_no_of(session, item.document_id),
                "section": item.section_code,
                "quote": item.source_text,
                "offset": [item.source_start, item.source_end],
            },
        })
    for f in session.scalars(
        select(ContraindicationFact).where(ContraindicationFact.item_id.in_(approved_ids))
    ).all():
        item = session.get(KnowledgeItem, f.item_id)
        contraindications.append({
            "subject": f.subject,
            "category": f.category,
            "source": {
                "doc_no": _doc_no_of(session, item.document_id),
                "section": item.section_code,
                "quote": item.source_text,
            },
        })

    now = dt.datetime.now()
    payload = {
        "version": now.strftime("%Y%m%d-%H%M%S"),
        "generated_at": now.isoformat(timespec="seconds"),
        "stats": {
            "interactions": len(interactions),
            "dosages": len(dosages),
            "contraindications": len(contraindications),
        },
        "interactions": interactions,
        "dosages": dosages,
        "contraindications": contraindications,
    }
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    checksum = hashlib.sha256(body.encode("utf-8")).hexdigest()
    payload["checksum"] = checksum

    out_path = EXPORT_DIR / f"kb_export_{payload['version']}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    session.add(ExportLog(
        export_path=str(out_path),
        item_count=sum(payload["stats"].values()),
        checksum=checksum,
    ))
    return {"path": str(out_path), "checksum": checksum, **payload["stats"]}
