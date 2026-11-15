"""章节标题归一化测试:覆盖各药厂五花八门的标题写法。"""
from app.parser.headings import normalize_heading


def test_gb_bracket_headings():
    assert normalize_heading("【药物相互作用】") == "interaction"
    assert normalize_heading("【用法用量】") == "dosage"
    assert normalize_heading("【禁忌】") == "contraindication"


def test_chinese_numbered_headings():
    assert normalize_heading("十二、药物相互作用") == "interaction"
    assert normalize_heading("五、禁忌") == "contraindication"
    assert normalize_heading("六、用法用量") == "dosage"


def test_arabic_alt_headings():
    assert normalize_heading("12. 药物交互作用") == "interaction"
    assert normalize_heading("5. 禁忌症") == "contraindication"
    assert normalize_heading("10. 小儿用药") == "pediatric"
    assert normalize_heading("16. 储存条件") == "storage"


def test_plain_synonym_headings():
    assert normalize_heading("与其他药物的相互作用") == "interaction"
    assert normalize_heading("禁用范围") == "contraindication"
    assert normalize_heading("给药途径及用量") == "dosage"
    assert normalize_heading("孕哺期用药") == "pregnancy"
    assert normalize_heading("上市许可持有人") == "manufacturer"


def test_parenthesized_numbering():
    assert normalize_heading("(一)药物相互作用") == "interaction"
    assert normalize_heading("（二）不良反应") == "adverse_reaction"


def test_non_heading_returns_empty():
    assert normalize_heading("华法林与阿司匹林合用增加出血风险。") == ""
    assert normalize_heading("") == ""
