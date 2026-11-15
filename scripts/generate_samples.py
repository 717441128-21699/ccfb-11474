"""500 份说明书样本生成器。

输出:
- data/raw/SMPLxxxxxx.docx|pdf:说明书原文(四套标题风格、两类文件格式)
- data/gold/gold_annotations.jsonl:逐文档人工标注(模拟),含相互作用/剂量/禁忌
- data/gold/manifest.json:文档清单与生成参数
- data/gold/annotation_guideline.md:标注规范(供真实药师标注沿用)

用法: py -m scripts.generate_samples --count 500
"""
from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path

from app.config import GOLD_DIR, RAW_DIR, ROOT_DIR
from app.normalize.canonical import canonical as _canon
from scripts.specs import INTERACTION_SPECS
from scripts.styles import MANUFACTURERS, STYLE_FAMILIES
from scripts.templates import add_typo, flip_direction, flip_severity, render_interaction

DICT_PATH = ROOT_DIR / "data" / "drug_dictionary.json"

# 剂量骨架(成人/儿童/肾/肝/老年),数值在生成时实例化
# freq_label -> 抽取器标准频次码,保证 gold 与系统同源
FREQ_CODE_BY_LABEL = {
    "每日1次": "QD", "每日2次": "Q12H", "每日3次": "TID",
    "每12小时1次": "Q12H", "每8小时1次": "Q8H", "每晚1次": "QN",
}
DOSAGE_TEMPLATES = {
    "adult": [
        ("成人推荐剂量为{dose},口服,{freq}。", "口服"),
        ("成人常规用量:{dose},餐后服用,{freq}。", "口服"),
        ("成人起始剂量{dose},{freq},{route},根据病情调整。", None),
        ("成人每次{dose},{freq},{route}。", None),
    ],
    "renal": [
        ("肾功能不全患者剂量调整为{dose},{freq},肌酐清除率低于30ml/min者减半。", ""),
        ("肾功能减退者推荐{dose},{freq},必要时延长给药间隔。", ""),
        ("肾损害患者起始剂量{dose},{freq},透析后补充一次。", ""),
    ],
    "hepatic": [
        ("肝功能不全患者慎用,推荐剂量{dose},{freq}。", ""),
        ("肝硬化患者剂量减为{dose},{freq},密切监测肝功能。", ""),
    ],
    "elderly": [
        ("老年患者无需调整剂量,常规{dose},{freq}。", ""),
        ("高龄患者建议从{dose}起始,{freq},谨慎加量。", ""),
    ],
}
CHILD_TEMPLATES = [
    "儿童按体重给药,{wb_dose}mg/kg,每日2次。",
    "小儿每日{wb_dose}mg/kg,分2~3次口服。",
    "婴幼儿用量为{wb_dose}mg/kg,{freq},遵医嘱。",
]
FREQ_LABELS = list(FREQ_CODE_BY_LABEL.keys())
DOSE_UNITS = ["mg", "mg", "mg", "g", "μg", "片"]  # mg 加权,避免出现 500g
ROUTES_INLINE = ["口服", "静脉滴注", "静脉注射"]

CONTRA_TEMPLATES = [
    "对本品任何成份过敏者禁用。",
    "{disease}患者禁用。",
    "孕妇及哺乳期妇女禁用。",
    "{disease}及严重肝肾功能不全者禁用。",
    "禁止与{drug}合用。",
    "有{disease}病史者禁忌使用。",
]
DISEASES = ["活动性消化性溃疡", "严重高血压", "支气管哮喘急性发作", "充血性心力衰竭",
            "严重肝功能不全", "严重肾功能不全", "出血性疾病", "青光眼",
            "重症肌无力", "粒细胞缺乏症"]


@dataclass
class GoldInteraction:
    drug_a: str
    drug_b: str
    pair_key: str
    interaction_type: str
    severity: str
    sentence: str


@dataclass
class GoldDosage:
    population: str
    dose_value: str
    dose_min: float | None
    dose_max: float | None
    dose_unit: str
    frequency: str
    route: str
    sentence: str


@dataclass
class GoldDoc:
    doc_no: str
    file_name: str
    file_type: str
    style_family: str
    generic_name: str
    manufacturer: str
    approval_no: str
    interactions: list[dict]
    dosages: list[dict]
    contraindications: list[dict]
    has_injected_contradiction: bool


def _load_drugs() -> list[dict]:
    return json.loads(DICT_PATH.read_text(encoding="utf-8"))


def _pick_display_name(rng: random.Random, entity: dict) -> str:
    """在通用名/商品名/别名中挑一个作为行文药名。"""
    pool = [entity["generic_name"], *entity.get("trade_names", []), *entity.get("aliases", [])]
    return rng.choice(pool)


def _entity_index(drugs: list[dict]) -> dict[str, dict]:
    idx = {}
    for e in drugs:
        for n in [e["generic_name"], *e.get("trade_names", []), *e.get("aliases", [])]:
            idx[n] = e
    return idx


def _build_doc_sections(rng: random.Random, doc: dict, style: str,
                        interactions: list[tuple], contradictions: list[tuple],
                        name_index: dict[str, dict]) -> dict[str, list[str]]:
    """生成各标准章节的正文行。interactions/contradictions 为规格元组列表。"""
    headings = STYLE_FAMILIES[style]
    generic = doc["generic_name"]
    sections: dict[str, list[str]] = {}

    sections["drug_name"] = [
        f"通用名称:{generic}",
        f"商品名称:{rng.choice(doc.get('trade_names') or ['—'])}",
        "英文名称:Simulated Preparation",
    ]
    sections["ingredient"] = [f"本品主要成份为{generic},辅料为淀粉、微晶纤维素、硬脂酸镁。"]
    sections["description"] = ["本品为薄膜衣片,除去包衣后显白色或类白色。"]
    sections["indication"] = [
        f"用于{generic}相关适应症的治疗,包括急性期控制与维持期管理。",
        "具体用法请遵医嘱。",
    ]

    # 禁忌章节
    contra_lines = [rng.choice(CONTRA_TEMPLATES).format(
        disease=rng.choice(DISEASES), drug=rng.choice(["其他同类制剂", "单胺氧化酶抑制剂"]))
        for _ in range(rng.randint(2, 3))]
    contra_lines.insert(0, "以下情况禁用:")
    sections["contraindication"] = contra_lines

    # 用法用量
    dose_lines, gold_dose, child_lines, gold_child = _build_dosage_lines(rng)
    sections["dosage"] = dose_lines
    sections["pediatric"] = child_lines
    sections["_gold_dosages"] = gold_dose + gold_child
    sections["geriatric"] = ["老年患者用药见用法用量,注意监测肝肾功能。"]
    sections["adverse_reaction"] = [
        "常见不良反应包括恶心、腹泻、头痛、皮疹,多为轻度至中度,停药后可缓解。",
        "偶见转氨酶升高、白细胞减少,出现持续异常应就医。",
    ]
    sections["precaution"] = [
        "用药前应询问过敏史,肝肾功能不全者慎用并注意剂量调整。",
        "长期用药应定期复查血常规与肝肾功能。",
    ]
    sections["pregnancy"] = ["孕妇及哺乳期妇女用药的安全性尚未确立,只有获益大于风险时方可使用。"]
    sections["overdose"] = ["药物过量可出现恶心、呕吐、嗜睡,应对症支持治疗,必要时血液净化。"]
    sections["pharmacology"] = ["本品作用于相应靶点,发挥治疗作用;毒理研究未见明显致癌致畸作用。"]
    sections["pharmacokinetics"] = ["口服吸收迅速,达峰时间1~2小时,主要经肝脏代谢,肾脏排泄。"]
    sections["storage"] = ["遮光,密封,在阴凉干燥处保存,温度不超过25℃。"]
    sections["packaging"] = ["铝塑泡罩包装,每盒2板,每板12片。"]
    sections["validity"] = ["24个月。"]
    sections["approval"] = [f"国药准字H{20000000 + rng.randrange(0, 9999999):07d}"]
    sections["manufacturer"] = [rng.choice(MANUFACTURERS)]

    # 药物相互作用(核心)
    inter_lines, gold_inter = _build_interaction_lines(
        rng, doc, interactions, contradictions, name_index)
    # 干扰句:不含药物对或不含触发词,考验精确率
    distractors = [
        "本品的药物相互作用研究数据有限。",
        "尚无相关药物相互作用的大规模临床研究。",
        "用药期间应注意观察患者反应。",
        "食物对本品吸收的影响不明显。",
    ]
    rng.shuffle(distractors)
    sections["interaction"] = inter_lines + distractors[:rng.randint(1, 2)]
    sections["_gold_interactions"] = gold_inter
    return sections


def _build_interaction_lines(rng, doc, interactions, contradictions, name_index):
    lines: list[str] = []
    gold: list[dict] = []
    generic = doc["generic_name"]
    for spec in interactions:
        a, b, itype, sev, effect = spec
        name_a = generic if a == generic else _pick_display_name(rng, name_index[a])
        name_b = _pick_display_name(rng, name_index[b])
        # 3% 错别字扰动
        if rng.random() < 0.03:
            name_b = add_typo(rng, name_b)
        sent = render_interaction(rng, name_a, name_b, itype, sev, effect)
        lines.append(sent)
        ca, cb = _canon(a), _canon(b)
        gold.append(asdict(GoldInteraction(
            drug_a=ca, drug_b=cb, pair_key="|".join(sorted([ca, cb])),
            interaction_type=itype, severity=sev, sentence=sent)))
    # 矛盾句(同一对,说法翻转)
    for spec in contradictions:
        a, b, itype, sev, effect = spec
        new_sev, new_type = flip_severity(rng, sev)
        if rng.random() < 0.5:
            new_type = flip_direction(itype)
        name_a = generic if a == generic else _pick_display_name(rng, name_index[a])
        name_b = _pick_display_name(rng, name_index[b])
        sent = render_interaction(rng, name_a, name_b, new_type, new_sev, effect)
        lines.append(sent)
        ca, cb = _canon(a), _canon(b)
        gold.append(asdict(GoldInteraction(
            drug_a=ca, drug_b=cb, pair_key="|".join(sorted([ca, cb])),
            interaction_type=new_type, severity=new_sev, sentence=sent)))
    return lines, gold


def _build_dosage_lines(rng) -> tuple[list[str], list[dict], list[str], list[dict]]:
    """返回(用法用量章节行, 该章节gold剂量, 儿童章节行, 儿童gold剂量)。"""
    lines: list[str] = []
    gold: list[dict] = []
    for pop in ["adult", "renal", "hepatic", "elderly"]:
        tpl, fixed_route = rng.choice(DOSAGE_TEMPLATES[pop])
        lo = rng.choice([5, 10, 20, 25, 50, 100, 200, 250])
        hi = lo * rng.choice([1, 1, 2])
        unit = rng.choice(DOSE_UNITS)
        dose = f"{lo}~{hi}{unit}" if hi != lo else f"{lo}{unit}"
        freq_label = rng.choice(FREQ_LABELS)
        route = fixed_route if fixed_route is not None else rng.choice(ROUTES_INLINE)
        line = tpl.format(dose=dose, freq=freq_label, route=route)
        lines.append(line)
        gold.append({
            "population": pop,
            "dose_value": dose,
            "dose_min": float(lo),
            "dose_max": float(hi) if hi != lo else None,
            "dose_unit": unit,
            "frequency": FREQ_CODE_BY_LABEL[freq_label],
            "frequency_label": freq_label,
            "route": route,
            "sentence": line,
        })

    # 儿童按体重(独立章节)
    wb = rng.choice([2.5, 5.0, 10.0, 15.0])
    wb_unit = "mg"
    child_line = rng.choice(CHILD_TEMPLATES).format(wb_dose=f"{wb:g}", freq="每日2次")
    child_gold = [{
        "population": "child",
        "dose_value": f"{wb:g}{wb_unit}/kg",
        "dose_min": wb, "dose_max": None,
        "dose_unit": f"{wb_unit}/kg",
        "frequency": "Q12H", "frequency_label": "每日2次",
        "route": "口服", "sentence": child_line,
    }]
    child_lines = ["新生儿不推荐使用。", child_line]
    return lines, gold, child_lines, child_gold


def generate(count: int, seed: int = 20261115) -> None:
    rng = random.Random(seed)
    drugs = _load_drugs()
    name_index = _entity_index(drugs)
    styles = list(STYLE_FAMILIES.keys())

    # 以每个药为「主药」轮排,保证 500 份覆盖全部品种
    base_drugs = [d for d in drugs if d["generic_name"] not in
                  {"乙醇", "葡萄柚汁", "碘造影剂", "含钙注射液"}]
    manifest: list[dict] = []
    gold_path = GOLD_DIR / "gold_annotations.jsonl"
    gf = gold_path.open("w", encoding="utf-8")

    # 规格按主药索引
    specs_by_drug: dict[str, list[tuple]] = {}
    for spec in INTERACTION_SPECS:
        specs_by_drug.setdefault(spec[0], []).append(spec)
        specs_by_drug.setdefault(spec[1], []).append(
            (spec[1], spec[0], spec[2], spec[3], spec[4]))

    # 预先决定哪些文档注入矛盾(约 8%),且矛盾对必须在另一份文档正常出现
    contradiction_plan: dict[int, list[tuple]] = {}
    doc_specs_cache: dict[int, list[tuple]] = {}
    for i in range(count):
        main = base_drugs[i % len(base_drugs)]
        pool = list(specs_by_drug.get(main["generic_name"], []))
        rng.shuffle(pool)
        if pool:
            k = rng.randint(1, min(5, len(pool)))
            chosen = pool[:k]
        else:
            chosen = []
        doc_specs_cache[i] = chosen

    # 选出矛盾对:同一 pair 在 >=2 个文档出现时,挑一个文档翻转
    pair_docs: dict[str, list[int]] = {}
    for i, specs in doc_specs_cache.items():
        for s in specs:
            key = "|".join(sorted([s[0], s[1]]))
            pair_docs.setdefault(key, []).append(i)
    multi_pairs = {k: v for k, v in pair_docs.items() if len(v) >= 2}
    spec_by_pair = {"|".join(sorted([s[0], s[1]])): s for s in INTERACTION_SPECS}
    injected = 0
    target_contradictions = max(30, count // 12)
    for key, doc_ids in rng.sample(sorted(multi_pairs.items()),
                                   min(target_contradictions, len(multi_pairs))):
        victim = rng.choice(doc_ids)
        contradiction_plan.setdefault(victim, []).append(spec_by_pair[key])
        injected += 1

    for i in range(count):
        main = base_drugs[i % len(base_drugs)]
        style = styles[i % len(styles)]
        file_type = "docx" if i % 10 < 6 else "pdf"   # 60% docx / 40% pdf
        doc_no = f"SMPL{i + 1:06d}"
        file_name = f"{doc_no}.{file_type}"
        contradictions = contradiction_plan.get(i, [])
        sections = _build_doc_sections(
            rng, main, style, doc_specs_cache[i], contradictions, name_index)
        gold_inter = sections.pop("_gold_interactions")
        gold_dosages = sections.pop("_gold_dosages")
        approval = f"国药准字H{20000000 + rng.randrange(0, 9999999):07d}"
        manufacturer = sections["manufacturer"][0]

        _write_file(RAW_DIR / file_name, style, sections)
        gold_doc = GoldDoc(
            doc_no=doc_no, file_name=file_name, file_type=file_type,
            style_family=style, generic_name=main["generic_name"],
            manufacturer=manufacturer, approval_no=approval,
            interactions=gold_inter,
            dosages=gold_dosages,
            contraindications=[{"subject": x, "category": "other"}
                               for x in sections["contraindication"][1:]],
            has_injected_contradiction=bool(contradictions),
        )
        gf.write(json.dumps(asdict(gold_doc), ensure_ascii=False) + "\n")
        manifest.append({
            "doc_no": doc_no, "file_name": file_name, "file_type": file_type,
            "style_family": style, "generic_name": main["generic_name"],
            "manufacturer": manufacturer,
        })

    gf.close()
    (GOLD_DIR / "manifest.json").write_text(
        json.dumps({"count": count, "seed": seed,
                    "injected_contradiction_docs": injected,
                    "styles": styles, "items": manifest},
                   ensure_ascii=False, indent=2),
        encoding="utf-8")
    _write_guideline()
    print(f"生成 {count} 份说明书 -> {RAW_DIR}")
    print(f"gold 标注 -> {gold_path};注入矛盾文档 {injected} 份")


def _write_file(path: Path, style: str, sections: dict[str, list[str]]) -> None:
    headings = STYLE_FAMILIES[style]
    ordered_codes = list(headings.keys())
    if path.suffix == ".docx":
        _write_docx(path, headings, ordered_codes, sections)
    else:
        _write_pdf(path, headings, ordered_codes, sections)


def _write_docx(path, headings, ordered_codes, sections):
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    doc.add_heading("药品说明书", level=1)
    for code in ordered_codes:
        if code not in sections:
            continue
        doc.add_paragraph(headings[code])
        for line in sections[code]:
            p = doc.add_paragraph(line)
            p.runs[0].font.size = Pt(10.5)
    doc.save(str(path))


def _write_pdf(path, headings, ordered_codes, sections):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    styles_sheet = getSampleStyleSheet()
    body = ParagraphStyle("cn", parent=styles_sheet["Normal"],
                          fontName="STSong-Light", fontSize=10, leading=15)
    head = ParagraphStyle("cnh", parent=body, fontSize=12, leading=18, spaceBefore=6)
    doc = SimpleDocTemplate(str(path), pagesize=A4,
                            leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm)
    story = [Paragraph("药品说明书", head)]
    for code in ordered_codes:
        if code not in sections:
            continue
        story.append(Paragraph(headings[code], head))
        for line in sections[code]:
            story.append(Paragraph(line, body))
        story.append(Spacer(1, 4))
    doc.build(story)


def _write_guideline() -> None:
    (GOLD_DIR / "annotation_guideline.md").write_text(
        "# 合理用药知识库人工标注规范(模拟标注沿用本规范)\n\n"
        "1. 相互作用:逐句标注药物对(统一为通用名)、作用类型、严重程度;无药物对或无联用触发词的句子不标。\n"
        "2. 严重程度:禁忌>高>中>低;含「禁用/严禁/避免合用」判禁忌;「显著/严重」判高;一般增强/增加判中;「轻度/影响较小」判低。\n"
        "3. 剂量:按成人/儿童/肾功能不全/肝功能不全/老年分别标注,用量拆数值与单位(区间填 min/max),频次用标准码,给药途径单独标注。\n"
        "4. 药名:商品名、别名全部归一到通用名,保留原文提及用于溯源。\n"
        "5. 每条标注必须能在原文定位到完整句子,出处偏移由系统自动计算,人工复核句子边界。\n"
        "6. 矛盾判定:同一药物对在不同说明书中出现禁忌vs非禁忌、严重程度跨两级、协同vs拮抗时,登记冲突。\n",
        encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=500)
    ap.add_argument("--seed", type=int, default=20261115)
    args = ap.parse_args()
    generate(args.count, args.seed)


if __name__ == "__main__":
    main()
