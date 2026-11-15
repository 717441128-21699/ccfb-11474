"""药名归一化与 canonical 短名映射测试。"""
from app.normalize.canonical import canonical
from app.normalize.drug_normalizer import DrugNormalizer, pair_key


def test_exact_generic_trade_alias():
    norm = DrugNormalizer()
    assert norm.normalize("华法林钠") == "华法林钠"
    assert norm.normalize("可达龙") == "胺碘酮"          # 商品名
    assert norm.normalize("乙酰水杨酸") == "阿司匹林"    # 别名
    assert norm.normalize("SMZco") == "复方磺胺甲噁唑"


def test_self_reference_resolution():
    norm = DrugNormalizer()
    mentions = norm.find_mentions("本品与阿司匹林合用", self_generic="华法林钠")
    names = {m.generic_name for m in mentions}
    assert "华法林钠" in names and "阿司匹林" in names


def test_fuzzy_typo_tolerance():
    norm = DrugNormalizer()
    # 精确匹配:商品名、别名全部归一到通用名
    assert norm.normalize("倍他乐克") == "酒石酸美托洛尔"
    assert norm.normalize("波立维") == "硫酸氢氯吡格雷"
    assert norm.normalize("络活喜") == "苯磺酸氨氯地平"
    assert norm.normalize("可达龙") == "胺碘酮"
    # 长名称(>=8 字)单字形近扰动,相似度仍可越过阈值
    long_name = "注射用头孢曲松钠"
    typo = long_name[:-1] + "衲"  # 末字替换
    assert norm.normalize(typo) == "注射用头孢曲松钠"


def test_canonical_strips_salt_prefix():
    assert canonical("美托洛尔") == "酒石酸美托洛尔"
    assert canonical("酒石酸美托洛尔") == "酒石酸美托洛尔"
    assert canonical("阿托伐他汀") == "阿托伐他汀钙"
    assert canonical("氯吡格雷") == "硫酸氢氯吡格雷"


def test_pair_key_is_order_independent():
    assert pair_key("A", "B") == pair_key("B", "A")
