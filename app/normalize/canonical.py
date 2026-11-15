"""通用名 canonical 映射:临床短名/盐基省略名 -> 词典标准通用名。

真实说明书与处方常省略盐基(盐酸/硫酸/酒石酸/苯磺酸/马来酸/醋酸/钙/钠),
gold 与抽取结果都经此映射后再比较,保证「美托洛尔」「酒石酸美托洛尔」等价。
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.config import ROOT_DIR

# 常见盐基/剂型前缀与后缀
_SALT_PREFIX = [
    "盐酸", "硫酸", "酒石酸", "苯磺酸", "马来酸", "醋酸", "甲磺酸", "氢溴酸",
    "乳酸", "葡萄糖酸", "琥珀酸", "富马酸", "磷酸", "硝酸", "枸橼酸",
]
_SALT_SUFFIX = ["钠", "钾", "钙"]
_DICT_PATH = ROOT_DIR / "data" / "drug_dictionary.json"


@lru_cache(maxsize=1)
def _canonical_table() -> dict[str, str]:
    entities = json.loads(_DICT_PATH.read_text(encoding="utf-8"))
    table: dict[str, str] = {}
    for ent in entities:
        g = ent["generic_name"]
        table[g] = g
        short = g
        for p in _SALT_PREFIX:
            if short.startswith(p):
                short = short[len(p):]
                break
        if len(short) >= 3 and short.endswith(tuple(_SALT_SUFFIX)):
            # 如「阿托伐他汀钙」->「阿托伐他汀」
            cand = short[:-1]
            if len(cand) >= 3:
                short = cand
        table.setdefault(short, g)
        for alias in ent.get("aliases", []):
            table.setdefault(alias, g)
    return table


def canonical(name: str) -> str:
    """归一到词典标准通用名;无法映射时原样返回。"""
    if not name:
        return name
    table = _canonical_table()
    if name in table:
        return table[name]
    # 再尝试剥盐基后查表
    short = name
    for p in _SALT_PREFIX:
        if short.startswith(p):
            short = short[len(p):]
            break
    return table.get(short, name)
