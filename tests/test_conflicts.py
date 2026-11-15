"""冲突判定逻辑单元测试(不依赖数据库)。"""
from types import SimpleNamespace

from app.extract.conflicts import _judge


def _fact(sev, itype):
    return SimpleNamespace(severity=sev, interaction_type=itype)


def test_contra_vs_non_has_priority():
    # 只要一份禁忌、另一份非禁忌,统一归 contra_vs_non(需求要求单独列出)
    assert _judge(_fact("禁忌", "酶抑制"), _fact("低", "其他")) == "contra_vs_non"
    assert _judge(_fact("禁忌", "酶抑制"), _fact("中", "其他")) == "contra_vs_non"


def test_severity_two_level_gap():
    assert _judge(_fact("高", "出血风险"), _fact("低", "出血风险")) == "severity_mismatch"


def test_one_level_gap_not_conflict():
    assert _judge(_fact("高", "出血风险"), _fact("中", "出血风险")) == ""


def test_opposing_effect_direction():
    assert _judge(_fact("中", "药效协同"), _fact("中", "拮抗/疗效降低")) == "effect_mismatch"


def test_same_claim_not_conflict():
    assert _judge(_fact("中", "出血风险"), _fact("中", "出血风险")) == ""
