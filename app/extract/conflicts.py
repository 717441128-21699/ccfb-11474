"""冲突检查:同一药物对在不同说明书中的说法矛盾。

矛盾类型:
- contra_vs_non:一份说禁忌/禁用,另一份为非禁忌
- severity_mismatch:严重程度跨越两个等级及以上(高 vs 低,禁忌 vs 中/低)
- effect_mismatch:一个是药效协同,另一个是拮抗/疗效降低(方向相反)
同一对文档同一 pair 只登记一条,取最强矛盾类型。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Conflict, Document, InteractionFact, KnowledgeItem

SEV_ORDER = {"禁忌": 4, "高": 3, "中": 2, "低": 1}


def _opposing_types(t1: str, t2: str) -> bool:
    return {t1, t2} == {"药效协同", "拮抗/疗效降低"}


def _judge(f1: InteractionFact, f2: InteractionFact) -> str:
    """矛盾类型判定。禁忌对立优先(需求要求单独列出禁忌类矛盾)。"""
    s1, s2 = SEV_ORDER.get(f1.severity, 2), SEV_ORDER.get(f2.severity, 2)
    # 1) 恰有一边是禁忌(另一边非禁忌)—— 优先单独归类
    severities = (f1.severity, f2.severity)
    if severities.count("禁忌") == 1:
        return "contra_vs_non"
    # 2) 作用方向相反(协同 vs 拮抗)
    if _opposing_types(f1.interaction_type, f2.interaction_type):
        return "effect_mismatch"
    # 3) 严重程度跨两级及以上
    if abs(s1 - s2) >= 2:
        return "severity_mismatch"
    return ""


def detect_conflicts(session: Session) -> list[Conflict]:
    facts = session.scalars(
        select(InteractionFact).join(KnowledgeItem,
                                     InteractionFact.item_id == KnowledgeItem.id)
        .where(KnowledgeItem.review_status != "rejected")
    ).all()
    items = {it.id: it for it in session.scalars(select(KnowledgeItem)).all()}
    docs = {d.id: d.doc_no for d in session.scalars(select(Document)).all()}

    # pair_key -> document_id -> 该文档下该 pair 的事实(同文档多条时保留最强)
    grouped: dict[str, dict[int, InteractionFact]] = {}
    for f in facts:
        doc_id = items[f.item_id].document_id
        slot = grouped.setdefault(f.pair_key, {}).get(doc_id)
        if slot is None or SEV_ORDER.get(f.severity, 2) > SEV_ORDER.get(slot.severity, 2):
            grouped[f.pair_key][doc_id] = f

    conflicts: list[Conflict] = []
    for pair_key_value, by_doc in grouped.items():
        if len(by_doc) < 2:
            continue
        doc_ids = sorted(by_doc.keys())
        registered: set[tuple[int, int]] = set()
        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                d1, d2 = doc_ids[i], doc_ids[j]
                f1, f2 = by_doc[d1], by_doc[d2]
                conflict_type = _judge(f1, f2)
                if not conflict_type or (d1, d2) in registered:
                    continue
                registered.add((d1, d2))
                conflicts.append(Conflict(
                    pair_key=pair_key_value,
                    drug_a=f1.drug_a, drug_b=f1.drug_b,
                    conflict_type=conflict_type,
                    item_id_1=f1.item_id, item_id_2=f2.item_id,
                    doc_no_1=docs[d1], doc_no_2=docs[d2],
                    detail=(
                        f"{docs[d1]}: {f1.severity}/{f1.interaction_type} "
                        f"vs {docs[d2]}: {f2.severity}/{f2.interaction_type}"
                    ),
                ))
    session.add_all(conflicts)
    return conflicts
