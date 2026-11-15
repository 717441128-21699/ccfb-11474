"""端到端流水线:文件 -> 解析 -> 切章节 -> 抽取 -> 持久化 -> 冲突检测。"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import PROCESSED_DIR
from app.db.models import (
    ContraindicationFact, Document, DosageFact, InteractionFact,
    KnowledgeItem, Section,
)
from app.extract.contraindication import extract_contraindications
from app.extract.dosage import extract_dosages
from app.extract.interaction import extract_interactions
from app.normalize.drug_normalizer import DrugNormalizer
from app.parser.readers import lines_to_text, read_document
from app.parser.sectioner import segment

_NORMALIZER: DrugNormalizer | None = None


def get_normalizer() -> DrugNormalizer:
    global _NORMALIZER
    if _NORMALIZER is None:
        _NORMALIZER = DrugNormalizer()
    return _NORMALIZER


@dataclass
class IngestResult:
    doc_no: str
    sections: int
    interactions: int
    dosages: int
    contraindications: int
    conflicts_added: int


def _delete_existing(session: Session, doc_id: int) -> None:
    item_ids = [row[0] for row in session.execute(
        delete(KnowledgeItem).where(KnowledgeItem.document_id == doc_id)
        .returning(KnowledgeItem.id)
    ).all()]
    if item_ids:
        for model in (InteractionFact, DosageFact, ContraindicationFact):
            session.execute(delete(model).where(model.item_id.in_(item_ids)))
    session.execute(delete(Section).where(Section.document_id == doc_id))


def ingest_file(session: Session, file_path: str | Path, doc_no: str,
                generic_name: str = "", manufacturer: str = "",
                approval_no: str = "", style_family: str = "") -> IngestResult:
    file_path = Path(file_path)
    lines = read_document(file_path)
    segmented = segment(lines)

    # 若未显式给通用名,尝试从文档元信息/药品名称章节推断
    if not generic_name:
        name_block = segmented.section_by_code.get("drug_name")
        generic_name = _guess_generic_name(name_block.text if name_block else "")

    # 重新入库(幂等)
    existing = session.query(Document).filter_by(doc_no=doc_no).one_or_none()
    if existing:
        _delete_existing(session, existing.id)
        doc = existing
    else:
        doc = Document(doc_no=doc_no, file_path=str(file_path),
                       file_type=file_path.suffix.lstrip("."))
        session.add(doc)
        session.flush()

    doc.title = f"{generic_name}说明书"
    doc.generic_name = generic_name
    doc.manufacturer = manufacturer
    doc.approval_no = approval_no
    doc.style_family = style_family
    doc.full_text = segmented.full_text

    for block in segmented.sections:
        session.add(Section(
            document_id=doc.id, code=block.code, raw_heading=block.raw_heading,
            text=block.text, order_index=block.order_index,
        ))
    session.flush()

    normalizer = get_normalizer()
    counts = {"interactions": 0, "dosages": 0, "contraindications": 0}

    # 1) 相互作用(偏移以章节正文在 full_text 中的基址为准)
    inter_block = segmented.section_by_code.get("interaction")
    if inter_block:
        for rec in extract_interactions(
            inter_block.text, inter_block.body_start_offset, normalizer, generic_name,
        ):
            item = KnowledgeItem(
                document_id=doc.id, item_type="interaction",
                section_code="interaction", source_text=rec.source_text,
                source_start=rec.source_start, source_end=rec.source_end,
                confidence=rec.confidence,
            )
            session.add(item)
            session.flush()
            session.add(InteractionFact(
                item_id=item.id, drug_a=rec.drug_a, drug_b=rec.drug_b,
                pair_key=rec.pair_key, interaction_type=rec.interaction_type,
                severity=rec.severity, effect_desc=rec.effect_desc,
                mentioned_a=rec.mentioned_a, mentioned_b=rec.mentioned_b,
            ))
            counts["interactions"] += 1

    # 2) 剂量(用法用量 + 儿童用药章节)
    dose_block = segmented.section_by_code.get("dosage")
    if dose_block:
        extra = []
        child_block = segmented.section_by_code.get("pediatric")
        if child_block:
            extra.append((child_block.text, child_block.body_start_offset))
        for rec in extract_dosages(dose_block.text, dose_block.body_start_offset, extra):
            item = KnowledgeItem(
                document_id=doc.id, item_type="dosage",
                section_code="dosage", source_text=rec.source_text,
                source_start=rec.source_start, source_end=rec.source_end,
                confidence=rec.confidence,
            )
            session.add(item)
            session.flush()
            session.add(DosageFact(
                item_id=item.id, population=rec.population,
                population_label=rec.population_label, dose_value=rec.dose_value,
                dose_min=rec.dose_min, dose_max=rec.dose_max,
                dose_unit=rec.dose_unit, frequency=rec.frequency,
                frequency_label=rec.frequency_label, route=rec.route,
                duration=rec.duration,
            ))
            counts["dosages"] += 1

    # 3) 禁忌
    contra_block = segmented.section_by_code.get("contraindication")
    if contra_block:
        for rec in extract_contraindications(
            contra_block.text, contra_block.body_start_offset):
            item = KnowledgeItem(
                document_id=doc.id, item_type="contraindication",
                section_code="contraindication", source_text=rec.source_text,
                source_start=rec.source_start, source_end=rec.source_end,
                confidence=rec.confidence,
            )
            session.add(item)
            session.flush()
            session.add(ContraindicationFact(
                item_id=item.id, subject=rec.subject, category=rec.category,
            ))
            counts["contraindications"] += 1

    # 落一份纯文本便于人工排查
    (PROCESSED_DIR / f"{doc_no}.txt").write_text(segmented.full_text, encoding="utf-8")

    return IngestResult(
        doc_no=doc_no, sections=len(segmented.sections),
        conflicts_added=0, **counts,
    )


def _guess_generic_name(text: str) -> str:
    """从药品名称章节文本里取第一行像通用名的内容。"""
    for line in text.splitlines():
        line = line.strip(" 　:：")
        if line and len(line) <= 30 and "商品名" not in line and "英文名" not in line:
            return line.split("：")[-1].split(":")[-1].strip()
    return ""
