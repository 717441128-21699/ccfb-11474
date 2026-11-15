"""禁忌抽取:从「禁忌」章节按句/分句生成禁忌知识条目,粗分人群/疾病/药物/其他。"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.extract.sentences import split_sentences

DISEASE_HINTS = ["病", "症", "溃疡", "哮喘", "高血压", "糖尿病", "衰竭", "梗死",
                 "硬化", "炎症", "出血", "贫血", "肿瘤", "障碍", "损伤", "昏迷"]
POPULATION_HINTS = ["孕妇", "妊娠", "哺乳", "儿童", "婴幼儿", "新生儿", "老年",
                    "过敏体质", "过敏史"]
DRUG_HINTS = ["药物", "药品", "制剂", "成分过敏", "类过敏"]
_SPLIT_RE = re.compile(r"[、,，;；]")


@dataclass
class ContraindicationRecord:
    subject: str
    category: str
    source_text: str
    source_start: int
    source_end: int
    confidence: float


def _categorize(subject: str) -> str:
    if any(h in subject for h in POPULATION_HINTS):
        return "population"
    if any(h in subject for h in DRUG_HINTS):
        return "drug"
    if any(h in subject for h in DISEASE_HINTS):
        return "disease"
    return "other"


def extract_contraindications(section_text: str, section_start: int) -> list[ContraindicationRecord]:
    records: list[ContraindicationRecord] = []
    for sent in split_sentences(section_text):
        text = sent.text.strip("。;；.")
        # 去掉常见引导语
        text = re.sub(r"^(以下情况|下列情况|对本品|本品)?(禁用|禁忌|忌用)[:：]?", "", text)
        if not text:
            continue
        pieces = [p.strip() for p in _SPLIT_RE.split(text) if len(p.strip()) >= 2]
        if not pieces:
            pieces = [text]
        for piece in pieces:
            records.append(ContraindicationRecord(
                subject=piece,
                category=_categorize(piece),
                source_text=sent.text,
                source_start=section_start + sent.start,
                source_end=section_start + sent.end,
                confidence=0.85,
            ))
    return records
