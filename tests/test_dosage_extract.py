"""剂量抽取:人群拆分、字段化、检验指标排除。"""
from app.extract.dosage import extract_dosages


def test_adult_dose_fields():
    text = "成人推荐剂量为100mg,口服,每日2次。"
    recs = extract_dosages(text, 0)
    assert len(recs) == 1
    r = recs[0]
    assert r.population == "adult"
    assert r.dose_value == "100mg"
    assert r.dose_min == 100 and r.dose_unit == "mg"
    assert r.frequency == "Q12H"
    assert r.route == "口服"


def test_dose_range_split_min_max():
    recs = extract_dosages("成人每次200~400mg,每日3次,口服。", 0)
    r = recs[0]
    assert r.dose_min == 200 and r.dose_max == 400
    assert r.frequency == "TID"


def test_population_classification():
    text = ("肾功能减退者推荐20mg,每日1次。\n"
            "肝功能不全患者慎用,推荐剂量50mg,每日1次。\n"
            "老年患者常规10mg,每日1次。")
    recs = extract_dosages(text, 0)
    pops = {r.population for r in recs}
    assert {"renal", "hepatic", "elderly"} <= pops


def test_weight_based_child_dose():
    child = "儿童按体重给药,10mg/kg,每日2次。"
    recs = extract_dosages("成人10mg,每日1次。", 0, [(child, 100)])
    child_recs = [r for r in recs if r.population == "child"]
    assert child_recs and child_recs[0].dose_value == "10mg/kg"
    assert child_recs[0].frequency == "Q12H"


def test_lab_value_not_treated_as_dose():
    text = "肾功能不全患者剂量调整为20mg,每日1次,肌酐清除率低于30ml/min者减半。"
    recs = extract_dosages(text, 0)
    values = {r.dose_value for r in recs}
    assert "30ml" not in values
    assert "20mg" in values
