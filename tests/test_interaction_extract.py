"""相互作用抽取:药物对、严重程度、作用类型、出处偏移。"""
from app.extract.interaction import extract_interactions
from app.normalize.drug_normalizer import DrugNormalizer

NORM = DrugNormalizer()


def _extract(text, self_name="华法林钠"):
    return extract_interactions(text, 0, NORM, self_name)


def test_basic_pair_and_fields():
    recs = _extract("华法林钠与阿司匹林合用,可显著增加出血的风险。")
    assert len(recs) == 1
    r = recs[0]
    assert r.drug_a == "华法林钠"
    assert r.drug_b == "阿司匹林"
    assert r.severity == "高"
    assert r.interaction_type == "出血风险"


def test_contraindication_severity():
    recs = _extract("利伐沙班与酮康唑合用,禁止联合使用,可引起出血。")
    assert recs and recs[0].severity == "禁忌"


def test_low_severity_qualifier_beats_generic_increase():
    recs = _extract("法莫替丁与阿卡波糖合并用药,仅轻度增加不良反应风险。",
                    self_name="法莫替丁")
    assert recs and recs[0].severity == "低"


def test_trade_name_and_alias_pairing():
    recs = _extract("华法林钠同可达龙联合使用,血药浓度显著升高,清除率下降风险明显增加。")
    assert recs and recs[0].drug_b == "胺碘酮"
    assert recs[0].interaction_type == "酶抑制"


def test_distractor_sentence_not_extracted():
    # 无药物对 / 无触发词的干扰句不应产生条目
    recs = _extract("本品的药物相互作用研究数据有限。")
    assert recs == []


def test_source_offsets_slice_back():
    text = "华法林钠与阿司匹林合用,可显著增加出血的风险。"
    recs = _extract(text)
    r = recs[0]
    assert text[r.source_start:r.source_end] == r.source_text


def test_multiple_drugs_in_sentence():
    recs = _extract("阿司匹林与布洛芬、华法林钠合用,出血风险增加。",
                    self_name="阿司匹林")
    pairs = {r.pair_key for r in recs}
    assert len(pairs) == 2
