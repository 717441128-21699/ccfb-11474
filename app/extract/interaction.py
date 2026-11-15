"""药物相互作用抽取。

输入章节文本与偏移,输出结构化 InteractionRecord:
- 药物对(归一化通用名、无序 pair_key、原文提及)
- 作用类型(酶抑制/酶诱导/出血风险/低血糖/低血压/…)
- 严重程度(禁忌/高/中/低)
- 原文出处句子与字符偏移
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import combinations

from app.extract.sentences import Sentence, split_sentences
from app.normalize.drug_normalizer import DrugNormalizer, Mention, pair_key

# ---- 文法词典 -------------------------------------------------------------

# 相互作用触发词:句子出现这些词才认为存在相互作用
INTERACTION_CUES = [
    "合用", "联用", "联合使用", "联合用药", "同时使用", "同用", "并用",
    "相互作用", "配伍", "一起使用", "共同使用", "合并用药", "联合应用",
    "与", "配合使用",
]

# 严重程度关键词(从强到弱,先命中先判定)
SEVERITY_RULES: list[tuple[str, list[str]]] = [
    ("禁忌", ["禁忌", "禁用", "严禁", "禁止", "不得", "避免合用",
              "不应合用", "不宜合用", "不可合用", "不能合用"]),
    ("高", ["显著", "明显", "严重", "大出血", "危及生命", "可导致死亡",
            "横纹肌溶解", "QT间期延长", "尖端扭转型", "呼吸抑制", "中毒"]),
    ("中", ["增加", "升高", "增强", "加强", "提高", "过度", "加重", "增高",
            "潴留", "蓄积", "协同", "低血糖", "出血", "低血压", "高钾",
            "惊厥", "镇静", "引起"]),
    ("低", ["轻度", "略有", "轻微", "小幅", "影响较小", "临床意义有限",
            "减弱", "降低", "下降", "减少", "拮抗", "抵消"]),
]
# 低级别修饰词:出现时压制泛化的中级别信号(如「仅轻度增加…」判低)
LOW_QUALIFIERS = ["轻度", "略有", "轻微", "小幅", "影响较小", "临床意义有限"]
# 高级别修饰词
HIGH_QUALIFIERS = ["显著", "明显", "严重"]
# 「严重低血糖」这类:严重是疾病名称的一部分,不代表相互作用等级高
_SEVERITY_DISEASE_TERMS = ["低血糖", "高钾血症", "低钾血症"]


def _detect_severity(sentence: str) -> str:
    # 1) 禁忌优先
    if any(kw in sentence for kw in SEVERITY_RULES[0][1]):
        return "禁忌"
    # 2) 低级别修饰词优先(仅轻度/略有/影响较小),避免被"增加"抢判
    if any(kw in sentence for kw in LOW_QUALIFIERS):
        return "低"
    # 3) 高级别修饰词,但排除「严重+疾病名」固定搭配
    high_hit = next((kw for kw in HIGH_QUALIFIERS if kw in sentence), "")
    if high_hit:
        rest = sentence
        for term in _SEVERITY_DISEASE_TERMS:
            rest = rest.replace("严重" + term, term).replace("明显" + term, term)
        if any(kw in rest for kw in HIGH_QUALIFIERS):
            return "高"
    # 4) 其他强信号
    if any(kw in sentence for kw in ["大出血", "危及生命", "可导致死亡",
                                     "横纹肌溶解", "呼吸抑制", "中毒"]):
        return "高"
    # 5) 中级别信号
    if any(kw in sentence for kw in SEVERITY_RULES[2][1]):
        return "中"
    if any(kw in sentence for kw in SEVERITY_RULES[3][1]):
        return "低"
    return "中"  # 有相互作用提示但无程度词,保守归中

# 作用类型关键词 -> 标准类型(关键词与 scripts/templates.py 效果词同源)
# 顺序即优先级:具体疾病/器官风险在前,酶抑制等泛代谢信号在后
TYPE_RULES: list[tuple[str, list[str]]] = [
    ("出血风险", ["出血", "出血倾向", "凝血", "抗凝作用增强", "INR", "血肿", "瘀斑"]),
    ("低血糖风险", ["低血糖", "降糖作用增强", "血糖过度"]),
    ("低血压风险", ["低血压", "降压过度", "血压过度下降"]),
    ("高钾血症", ["高钾", "血钾升高", "高钾血症"]),
    ("QT延长/心律失常", ["QT", "心律失常", "尖端扭转", "心动过缓", "传导阻滞"]),
    ("肌病风险", ["肌病", "肌溶解", "横纹肌溶解", "横纹肌", "肌肉毒性"]),
    ("惊厥风险", ["惊厥", "癫痫发作", "抽搐阈值"]),
    ("中枢抑制", ["嗜睡", "镇静过度", "呼吸抑制", "中枢抑制", "昏迷"]),
    ("骨髓抑制", ["骨髓抑制", "粒细胞缺乏", "白细胞减少", "血小板减少"]),
    ("肾毒性", ["肾毒性", "肾功能损害", "肾功能损伤", "肾损伤", "肾衰"]),
    ("肝毒性", ["肝毒性", "肝损伤", "肝功能损害"]),
    ("电解质紊乱", ["低钠", "低钾", "低钾血症", "低钙", "电解质紊乱"]),
    ("拮抗/疗效降低", ["拮抗", "疗效降低", "作用减弱", "效果下降", "抵消",
                        "降效", "抗菌活性降低", "活性降低"]),
    ("药效协同", ["药效协同", "协同增强", "效应增强", "疗效增强", "药效增强",
                  "作用增强"]),
    ("酶诱导", ["酶诱导", "诱导CYP", "代谢加快", "肝药酶诱导", "诱导肝药酶",
                "CYP3A4诱导", "血药浓度降低", "排泄加快", "代谢加速"]),
    ("酶抑制", ["CYP3A4抑制", "酶抑制", "抑制CYP", "代谢减慢", "代谢被抑制",
                "肝药酶抑制", "CYP2C9抑制", "CYP2D6抑制", "清除率下降",
                "清除降低", "血药浓度升高", "浓度升高"]),
    ("其他", []),
]

# 强提示:句首/并列结构
_PAIR_CUE_RE = re.compile(r"(与|和|同|跟|联合|合用|联用|配伍|同时)")


@dataclass
class InteractionRecord:
    drug_a: str
    drug_b: str
    pair_key: str
    interaction_type: str
    severity: str
    effect_desc: str
    mentioned_a: str
    mentioned_b: str
    source_text: str
    source_start: int
    source_end: int
    confidence: float
    match_types: tuple[str, str] = field(default_factory=tuple)


def _detect_type(sentence: str) -> str:
    for std_type, kws in TYPE_RULES:
        if kws and any(kw in sentence for kw in kws):
            return std_type
    return "其他"


def _has_cue(sentence: str) -> bool:
    return any(cue in sentence for cue in INTERACTION_CUES)


def _build_pairs(mentions: list[Mention], self_generic: str) -> list[tuple[Mention, Mention]]:
    """同句药物提及 -> 药物对。

    - 含自指(本品)时:自指与每个其他药成对;
    - 否则:同句不同通用名两两成对(同句通常 2~3 个药)。
    """
    uniq: dict[str, Mention] = {}
    for m in mentions:
        uniq.setdefault(m.generic_name, m)
    drugs = list(uniq.values())
    pairs: list[tuple[Mention, Mention]] = []
    self_mentions = [m for m in drugs if m.generic_name == self_generic]
    others = [m for m in drugs if m.generic_name != self_generic]
    if self_mentions and others:
        anchor = self_mentions[0]
        for other in others:
            pairs.append((anchor, other))
    else:
        for a, b in combinations(drugs, 2):
            pairs.append((a, b))
    return pairs[:4]  # 单句上限,防御性截断


def extract_interactions(
    section_text: str,
    section_start: int,
    normalizer: DrugNormalizer,
    self_generic: str,
) -> list[InteractionRecord]:
    records: list[InteractionRecord] = []
    seen: set[tuple[str, int]] = set()  # 同 pair 同句去重
    for sent in split_sentences(section_text):
        if not _has_cue(sent.text):
            continue
        mentions = normalizer.find_mentions(sent.text, self_generic=self_generic)
        distinct = {m.generic_name for m in mentions}
        if len(distinct) < 2:
            continue
        severity = _detect_severity(sent.text)
        inter_type = _detect_type(sent.text)
        for a, b in _build_pairs(mentions, self_generic):
            key = pair_key(a.generic_name, b.generic_name)
            dedup = (key, sent.start)
            if dedup in seen:
                continue
            seen.add(dedup)
            conf = 0.95
            if "fuzzy" in (a.match_type, b.match_type):
                conf -= 0.1
            if not _PAIR_CUE_RE.search(sent.text):
                conf -= 0.05
            records.append(InteractionRecord(
                drug_a=a.generic_name,
                drug_b=b.generic_name,
                pair_key=key,
                interaction_type=inter_type,
                severity=severity,
                effect_desc=sent.text,
                mentioned_a=a.text,
                mentioned_b=b.text,
                source_text=sent.text,
                source_start=section_start + sent.start,
                source_end=section_start + sent.end,
                confidence=round(conf, 3),
                match_types=(a.match_type, b.match_type),
            ))
    return records
