"""抽取质量评估:以 gold 标注为基准,计算精确率/召回率/F1。

三层相互作用指标:
- pair:药物对识别(无序 pair_key)
- pair_severity:药物对 + 严重程度
- pair_full:药物对 + 严重程度 + 作用类型
另含剂量(population+dose_value+frequency)与章节切分指标。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import GOLD_DIR
from app.db.models import Document, DosageFact, InteractionFact, KnowledgeItem, Section
from app.normalize.canonical import canonical
from app.normalize.drug_normalizer import pair_key

# 样本每份说明书包含的标准章节(与 scripts/styles.py 样式表一致)
STYLE_SECTION_CODES = [
    "drug_name", "ingredient", "description", "indication", "contraindication",
    "dosage", "adverse_reaction", "precaution", "pregnancy", "pediatric",
    "geriatric", "interaction", "overdose", "pharmacology", "pharmacokinetics",
    "storage", "packaging", "validity", "approval", "manufacturer",
]


@dataclass
class Metric:
    name: str
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    def as_row(self) -> dict:
        return {"name": self.name, "tp": self.tp, "fp": self.fp, "fn": self.fn,
                "precision": round(self.precision, 4),
                "recall": round(self.recall, 4), "f1": round(self.f1, 4)}


def load_gold() -> dict[str, dict]:
    path = GOLD_DIR / "gold_annotations.jsonl"
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        out[rec["doc_no"]] = rec
    return out


def evaluate(session: Session) -> dict:
    gold = load_gold()
    m_pair = Metric("interaction_pair")
    m_sev = Metric("interaction_pair_severity")
    m_full = Metric("interaction_full_typed")
    m_dose = Metric("dosage_fields")
    m_section = Metric("section_segmentation")

    docs = session.scalars(select(Document)).all()
    for doc in docs:
        g = gold.get(doc.doc_no)
        if not g:
            continue

        # ---- 相互作用(同文档同 pair 可有多条,按字段逐一配对) ----
        pred_items = session.scalars(
            select(InteractionFact).join(KnowledgeItem,
                                         InteractionFact.item_id == KnowledgeItem.id)
            .where(KnowledgeItem.document_id == doc.id)
        ).all()
        gold_records = [{**x,
                         "pair_key": pair_key(canonical(x["drug_a"]),
                                              canonical(x["drug_b"]))}
                        for x in g["interactions"]]
        pred_records = [{"pair_key": pair_key(canonical(f.drug_a),
                                              canonical(f.drug_b)),
                         "severity": f.severity,
                         "interaction_type": f.interaction_type} for f in pred_items]

        def _match_level(gx: dict, px: dict) -> int:
            """0=不匹配 1=pair 2=pair+严重程度 3=全字段。"""
            if gx["pair_key"] != px["pair_key"]:
                return 0
            if gx["severity"] != px["severity"]:
                return 1
            if gx["interaction_type"] != px["interaction_type"]:
                return 2
            return 3

        # 贪心:每个 gold 选当前未占用的最高匹配层级预测
        used_pred = set()
        for gx in gold_records:
            best_idx, best_level = -1, 0
            for idx, px in enumerate(pred_records):
                if idx in used_pred:
                    continue
                level = _match_level(gx, px)
                if level > best_level:
                    best_level, best_idx = level, idx
            if best_level == 0:
                m_pair.fn += 1
                m_sev.fn += 1
                m_full.fn += 1
            else:
                used_pred.add(best_idx)
                m_pair.tp += 1
                if best_level >= 2:
                    m_sev.tp += 1
                else:
                    m_sev.fn += 1
                if best_level == 3:
                    m_full.tp += 1
                else:
                    m_full.fn += 1
        for idx, px in enumerate(pred_records):
            if idx not in used_pred:
                m_pair.fp += 1
                m_sev.fp += 1
                m_full.fp += 1

        # ---- 剂量 ----
        pred_doses = session.scalars(
            select(DosageFact).join(KnowledgeItem,
                                    DosageFact.item_id == KnowledgeItem.id)
            .where(KnowledgeItem.document_id == doc.id)
        ).all()
        pred_dose_keys = {(d.population, d.dose_value, d.frequency) for d in pred_doses}
        gold_dose_keys = {(d["population"], d["dose_value"], d["frequency"])
                          for d in g["dosages"]}
        m_dose.tp += len(pred_dose_keys & gold_dose_keys)
        m_dose.fp += len(pred_dose_keys - gold_dose_keys)
        m_dose.fn += len(gold_dose_keys - pred_dose_keys)

        # ---- 章节切分:样本每份都含 20 个标准章节(见生成器样式表) ----
        pred_codes = {s.code for s in
                      session.scalars(select(Section).where(Section.document_id == doc.id)).all()}
        gold_codes = set(STYLE_SECTION_CODES)
        m_section.tp += len(pred_codes & gold_codes)
        m_section.fp += len(pred_codes - gold_codes)
        m_section.fn += len(gold_codes - pred_codes)

    metrics = [m_pair, m_sev, m_full, m_dose, m_section]
    return {
        "docs": len(docs),
        "metrics": [m.as_row() for m in metrics],
        "targets_met": {
            "interaction_pair_precision_ge_90": m_pair.precision >= 0.90,
            "interaction_pair_recall_ge_90": m_pair.recall >= 0.90,
            "interaction_full_precision_ge_90": m_full.precision >= 0.90,
            "interaction_full_recall_ge_90": m_full.recall >= 0.90,
        },
    }
