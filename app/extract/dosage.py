"""剂量抽取:按人群(成人/儿童/肾功能不全/肝功能不全/老年)拆分,
用量(数值+单位+区间)与频次、给药途径拆成独立字段。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.extract.sentences import split_sentences

# 人群判定关键词(按特异性从高到低)
POPULATION_RULES: list[tuple[str, list[str]]] = [
    ("renal", ["肾功能不全", "肾功能减退", "肾损害", "肾损伤", "肾功能受损",
               "肾衰竭", "肌酐清除率", "透析", "CKD"]),
    ("hepatic", ["肝功能不全", "肝功能减退", "肝损害", "肝损伤", "肝功能受损",
                 "肝硬化", "肝功能异常"]),
    ("child", ["儿童", "小儿", "婴幼儿", "新生儿", "患儿", "儿科", "未成年",
               "月龄", "体重", "kg", "公斤"]),
    ("elderly", ["老年", "高龄", "老人"]),
    ("adult", ["成人", "成年人", "常规剂量", "推荐剂量", "常用量", "每日",
               "每次", "口服", "静脉", "起始剂量", "维持剂量"]),
]
POPULATION_LABELS = {
    "adult": "成人", "child": "儿童", "renal": "肾功能不全",
    "hepatic": "肝功能不全", "elderly": "老年",
}

# 频次标准化
FREQUENCY_RULES: list[tuple[str, str, list[str]]] = [
    ("Q4H", "每4小时1次", ["每4小时", "q4h"]),
    ("Q6H", "每6小时1次", ["每6小时", "q6h"]),
    ("Q8H", "每8小时1次", ["每8小时", "q8h"]),
    ("Q12H", "每12小时1次", ["每12小时", "q12h", "每日2次", "一日2次",
                              "每天2次", "每日两次", "一日两次", "一天2次",
                              "2次/日", "bid", "分2次", "分2~3次",
                              "分2至3次", "分2-3次"]),
    ("QD", "每日1次", ["每日1次", "一日1次", "每天1次", "每日一次",
                        "一日一次", "1次/日", "qd", "每日顿服", "顿服"]),
    ("QN", "每晚1次", ["每晚", "睡前", "qn"]),
    ("TID", "每日3次", ["每日3次", "一日3次", "每天3次", "每日三次",
                         "一日三次", "3次/日", "tid", "分3次"]),
    ("QID", "每日4次", ["每日4次", "一日4次", "每天4次", "每日四次",
                         "4次/日", "qid"]),
    ("PRN", "必要时", ["必要时", "需要时", "prn", "sos"]),
    ("WEEKLY", "每周1次", ["每周1次", "每周一次", "一周1次", "每周"]),
]

ROUTE_RULES: list[tuple[str, list[str]]] = [
    ("口服", ["口服", "内服", "吞服", "嚼服", "餐前服用", "餐后服用", "空腹服用"]),
    ("静脉滴注", ["静脉滴注", "静滴", "输液", "滴注"]),
    ("静脉注射", ["静脉注射", "静注"]),
    ("肌内注射", ["肌内注射", "肌注"]),
    ("皮下注射", ["皮下注射", "皮注"]),
    ("外用", ["外用", "局部涂抹", "涂于患处"]),
    ("吸入", ["吸入", "雾化"]),
]
_FREQ_LABELS = {code: label for code, label, _ in FREQUENCY_RULES}

# 数值+单位,支持区间(10~20mg / 10-20 mg / 0.25~0.5 g)
DOSE_RE = re.compile(
    r"(?P<min>\d+(?:\.\d+)?)\s*(?:[-~～至到]\s*(?P<max>\d+(?:\.\d+)?)\s*)?"
    r"(?P<unit>mg|g|μg|ug|IU|U|片|粒|袋|支|单位|毫克|克|微克)"
)
WEIGHT_BASED_RE = re.compile(r"(?P<dose>\d+(?:\.\d+)?)\s*(?P<unit>mg|g|μg|ug)\s*/\s*kg")
# 检验指标型数值,不是给药剂量(肌酐清除率、化验阈值等)
LAB_VALUE_RE = re.compile(
    r"(肌酐清除率|CrCl|eGFR|肾小球滤过率|清除率)[^。;；\n]{0,12}"
    r"\d+(?:\.\d+)?\s*(?:ml|mL|μmol|mmol|%)")


def _is_lab_value(sentence: str, match: re.Match) -> bool:
    for lab in LAB_VALUE_RE.finditer(sentence):
        if lab.start() <= match.start() < lab.end():
            return True
    return False


@dataclass
class DosageRecord:
    population: str
    population_label: str
    dose_value: str
    dose_min: float | None
    dose_max: float | None
    dose_unit: str
    frequency: str
    frequency_label: str
    route: str
    duration: str
    source_text: str
    source_start: int
    source_end: int
    confidence: float


def _classify_population(sentence: str) -> str:
    for pop, kws in POPULATION_RULES:
        if any(kw in sentence for kw in kws):
            return pop
    return "adult"  # 用法用量章节默认成人


def _detect_frequency(sentence: str) -> tuple[str, str]:
    low = sentence.lower()
    for code, label, kws in FREQUENCY_RULES:
        if any(kw.lower() in low for kw in kws):
            return code, label
    return "", ""


def _detect_route(sentence: str) -> str:
    for route, kws in ROUTE_RULES:
        if any(kw in sentence for kw in kws):
            return route
    return ""


def _extract_dose(sentence: str) -> tuple[str, float | None, float | None, str]:
    wm = WEIGHT_BASED_RE.search(sentence)
    if wm:
        val = f"{wm.group('dose')}{wm.group('unit')}/kg"
        return val, float(wm.group("dose")), None, wm.group("unit") + "/kg"
    m = DOSE_RE.search(sentence)
    if not m:
        return "", None, None, ""
    lo = float(m.group("min"))
    hi = float(m.group("max")) if m.group("max") else None
    unit = m.group("unit")
    value = m.group(0).replace(" ", "")
    return value, lo, hi, unit


def extract_dosages(
    section_text: str,
    section_start: int,
    extra_sections: list[tuple[str, int]] | None = None,
) -> list[DosageRecord]:
    """extra_sections: 其他可含剂量信息的章节 (text, start),如儿童用药。"""
    sources = [("dosage", section_text, section_start)]
    if extra_sections:
        sources.extend(("extra", t, s) for t, s in extra_sections)

    records: list[DosageRecord] = []
    seen: set[tuple[str, str, int]] = set()
    for src_kind, text, start in sources:
        sentences = split_sentences(text)
        # 预扫描:章节级人群提示(如儿童用药章节),用于只有数值的分句
        section_pop = _classify_population(text) if src_kind == "extra" else ""
        prev_pop, prev_freq, prev_route = "", "", ""
        for sent in sentences:
            # 一句可能含多个剂量(分号/逗号列举),逐个抽取并按数值位置切子串
            dose_matches = list(DOSE_RE.finditer(sent.text))
            wb_matches = list(WEIGHT_BASED_RE.finditer(sent.text))
            if not dose_matches and not wb_matches:
                continue
            # 本句无人群关键词时,继承章节人群或上一句(分号列举句)
            pop = _classify_population(sent.text)
            if pop == "adult" and (section_pop or prev_pop):
                pop = section_pop or prev_pop
            # 体重剂量天然属于儿童
            if wb_matches:
                pop = "child"
            freq_code, freq_label = _detect_frequency(sent.text)
            if not freq_code and prev_freq:
                freq_code, freq_label = prev_freq, _FREQ_LABELS.get(prev_freq, "")
            route = _detect_route(sent.text) or prev_route
            prev_pop, prev_freq, prev_route = pop, freq_code, route
            # 体重剂量优先(儿童章节)
            for wm in wb_matches:
                if _is_lab_value(sent.text, wm):
                    continue
                value = f"{wm.group('dose')}{wm.group('unit')}/kg"
                dedup = ("child", value, sent.start)
                if dedup in seen:
                    continue
                seen.add(dedup)
                records.append(DosageRecord(
                    population="child", population_label=POPULATION_LABELS["child"],
                    dose_value=value, dose_min=float(wm.group("dose")), dose_max=None,
                    dose_unit=wm.group("unit") + "/kg",
                    frequency=freq_code, frequency_label=freq_label,
                    route=route or "口服", duration="",
                    source_text=sent.text,
                    source_start=start + sent.start, source_end=start + sent.end,
                    confidence=0.9 if freq_code else 0.75,
                ))
            for m in dose_matches:
                # 跳过体重剂量(如 10mg/kg)中已按 wb 处理的数值段
                if any(wm.start() <= m.start() < wm.end() for wm in wb_matches):
                    continue
                # 跳过检验指标数值(肌酐清除率 30ml/min 等)
                if _is_lab_value(sent.text, m):
                    continue
                lo = float(m.group("min"))
                hi = float(m.group("max")) if m.group("max") else None
                unit = m.group("unit")
                value = m.group(0).replace(" ", "")
                dedup = (pop, value, sent.start)
                if dedup in seen:
                    continue
                seen.add(dedup)
                records.append(DosageRecord(
                    population=pop,
                    population_label=POPULATION_LABELS[pop],
                    dose_value=value, dose_min=lo, dose_max=hi, dose_unit=unit,
                    frequency=freq_code, frequency_label=freq_label,
                    route=route, duration="",
                    source_text=sent.text,
                    source_start=start + sent.start, source_end=start + sent.end,
                    confidence=0.9 if freq_code else 0.75,
                ))
    return records
