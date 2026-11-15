"""句式模板引擎:把相互作用规格渲染成风格各异的中文句子。

设计原则:
- 每条规格可由多个模板族渲染,模板覆盖各药厂行文风格(条目式/散文式/警示式);
- 程度词、类型效果词集中在本模块常量,抽取器文法表与之一一对应(见 interaction.py);
- 支持药名换商品名/别名、轻微错别字扰动;
- 同一规格在不同文档可渲染为「矛盾版本」(严重程度/方向翻转)。
"""
from __future__ import annotations

import random

# 严重程度 -> 程度子句模板(关键词与抽取器 SEVERITY_RULES 对应)
SEVERITY_PHRASES: dict[str, list[str]] = {
    "禁忌": [
        "属禁忌合用药物,严禁合用,可致{effect}",
        "禁止联合使用,可引起{effect}",
        "不得同用,避免合用,存在{effect}风险",
        "合用属禁忌,不应联用,可导致{effect}",
    ],
    "高": [
        "可显著增加{effect}的风险",
        "导致{effect},风险显著增加",
        "引起严重的{effect}",
        "血药浓度显著升高,{effect}风险明显增加",
        "存在明显的{effect}风险",
    ],
    "中": [
        "可能增加{effect}的风险",
        "使{effect}风险增高",
        "可引起{effect}",
        "导致血药浓度升高,{effect}风险增加",
        "合用时{effect}风险增加",
    ],
    "低": [
        "对{effect}影响较小",
        "仅轻度增加{effect}风险",
        "可能轻微影响{effect}",
        "{effect}略有变化,临床意义有限",
    ],
}

# 作用类型 -> 效果核心词(全部收录在抽取器 TYPE_RULES 关键词中)
TYPE_EFFECT_WORDS: dict[str, list[str]] = {
    "酶抑制": ["代谢减慢", "血药浓度升高", "清除率下降"],
    "酶诱导": ["代谢加快", "血药浓度降低", "排泄加快"],
    "出血风险": ["出血", "消化道出血", "出血倾向"],
    "低血糖风险": ["低血糖", "严重低血糖"],
    "低血压风险": ["低血压", "血压过度下降"],
    "高钾血症": ["高钾血症", "血钾升高"],
    "QT延长/心律失常": ["QT间期延长", "心律失常"],
    "肾毒性": ["肾毒性", "肾功能损害"],
    "肝毒性": ["肝毒性", "肝损伤"],
    "骨髓抑制": ["骨髓抑制", "粒细胞缺乏"],
    "肌病风险": ["肌病", "横纹肌溶解"],
    "中枢抑制": ["镇静过度", "呼吸抑制", "嗜睡"],
    "拮抗/疗效降低": ["疗效降低", "抗菌活性降低", "作用减弱"],
    "药效协同": ["药效协同增强", "作用增强"],
    "电解质紊乱": ["低钾血症", "电解质紊乱"],
    "惊厥风险": ["惊厥", "癫痫发作"],
    "其他": ["不良反应", "相互作用"],
}

# 句子骨架:保证每个都含联用触发词(合用/联用/与…同用 等)
# {tail} 已携带与规格严重程度一致的程度词,避免出现无程度线索的裸句
SENTENCE_TEMPLATES = [
    "{a}与{b}合用,{tail}。",
    "{a}和{b}联用,{tail}。",
    "{a}同{b}联合使用,{tail}。",
    "临床中{a}与{b}同时使用,{tail}。",
    "治疗上{a}与{b}联合应用,{tail}。",
    "体外及临床研究表明,{a}与{b}合用,{tail}。",
    "有报道指出,{a}与{b}联用,{tail}。",
    "联合用药提示:{a}与{b}合用,{tail}。",
    "若患者正在使用{b},{a}与其合用,{tail}。",
    "{a}与{b}合并用药,{tail}。",
]


def render_interaction(rng: random.Random, name_a: str, name_b: str,
                       inter_type: str, severity: str, effect_core: str) -> str:
    """渲染一条相互作用句子。"""
    effect_word = rng.choice(TYPE_EFFECT_WORDS.get(inter_type, ["不良反应"]))
    if severity == "禁忌":
        # 禁忌句保留效果词,使作用类型仍可被识别
        tail = rng.choice(SEVERITY_PHRASES["禁忌"]).format(b=name_b, effect=effect_word)
        template = rng.choice([
            "{a}与{b}合用," + tail + "。",
            "{a}:" + tail + "({b})。",
        ])
        return template.format(a=name_a, b=name_b)
    tail = rng.choice(SEVERITY_PHRASES[severity]).format(b=name_b, effect=effect_word)
    template = rng.choice(SENTENCE_TEMPLATES)
    return template.format(a=name_a, b=name_b, tail=tail)


# 矛盾翻转:同一药物对的另一份说明书给出不同说法
def flip_severity(rng: random.Random, severity: str) -> tuple[str, str]:
    """返回(新严重程度, 新作用类型)。"""
    if severity == "禁忌":
        return rng.choice(["中", "低"]), "其他"
    if severity == "高":
        return "低", "其他"
    if severity == "中":
        return rng.choice(["禁忌", "高"]), rng.choice(["酶抑制", "出血风险", "其他"])
    return rng.choice(["中", "高"]), "其他"


def flip_direction(inter_type: str) -> str:
    if inter_type == "药效协同":
        return "拮抗/疗效降低"
    if inter_type == "拮抗/疗效降低":
        return "药效协同"
    if inter_type == "酶抑制":
        return "酶诱导"
    if inter_type == "酶诱导":
        return "酶抑制"
    return inter_type


# 名称扰动:模拟真实 OCR/录入错误,严格限制为单字级别(一次仅替换一个字),
# 与 normalizer 的 RapidFuzz 容错阈值(88)能力匹配;不做双字换位/漏字这类过重扰动
_HOMOPHONES = {
    "林": "淋", "克": "刻", "泮": "半", "胍": "瓜", "吡": "比",
    "嗪": "秦", "普": "朴", "霉": "梅", "蝶": "喋",
}


def add_typo(rng: random.Random, name: str) -> str:
    if len(name) < 3:
        return name
    # 优先近音字替换(单字)
    for k, v in _HOMOPHONES.items():
        if k in name and rng.random() < 0.7:
            return name.replace(k, v, 1)
    # 否则在药名内部做一次相邻字交换(仅一次,且不动首尾)
    if len(name) >= 4:
        i = rng.randrange(1, len(name) - 2)
        chars = list(name)
        chars[i], chars[i + 1] = chars[i + 1], chars[i]
        return "".join(chars)
    return name
