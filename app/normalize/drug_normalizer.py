"""药名归一化:原文药名 -> 标准通用名。

策略:
1. 词典全量名称(通用名/商品名/别名)精确匹配,长名优先;
2. 限定长度的滑动窗口 + RapidFuzz 模糊匹配,容忍同音字/错字;
3. 「本品」「本药」回填为当前说明书的通用名。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz

from app.config import FUZZY_MATCH_THRESHOLD, ROOT_DIR

DICT_PATH = ROOT_DIR / "data" / "drug_dictionary.json"
SELF_REFERENCES = ("本品", "本药", "该药", "此药", "本制剂", "本品种")


@dataclass
class Mention:
    text: str           # 原文片段
    start: int          # 在句子中的偏移
    end: int
    generic_name: str   # 归一化后的通用名
    match_type: str     # exact / fuzzy / self


class DrugNormalizer:
    def __init__(self, dict_path: str | Path = DICT_PATH) -> None:
        raw = json.loads(Path(dict_path).read_text(encoding="utf-8"))
        self.entities = raw
        self.generic_names: list[str] = [e["generic_name"] for e in raw]
        # 名称 -> 通用名
        self._exact: dict[str, str] = {}
        for ent in raw:
            for name in [ent["generic_name"], *ent.get("trade_names", []), *ent.get("aliases", [])]:
                self._exact[name] = ent["generic_name"]
        # 长名优先,避免"氨氯地平"抢先匹配"苯磺酸氨氯地平"
        self._all_names = sorted(self._exact.keys(), key=len, reverse=True)
        # 模糊匹配候选:长度 >=2(含"速尿""可达龙"这类短别名),按长度降序
        self._fuzzy_names = sorted(set(n for n in self._all_names if len(n) >= 2),
                                   key=len, reverse=True)

    @lru_cache(maxsize=4096)
    def normalize(self, text: str) -> str | None:
        """单个药名归一化。"""
        if text in self._exact:
            return self._exact[text]
        best = (None, 0)
        for name in self._fuzzy_names:
            if abs(len(name) - len(text)) > 3:
                continue
            score = max(fuzz.ratio(text, name),
                        fuzz.partial_ratio(text, name) - 4)
            if score > best[1]:
                best = (name, score)
        if best[1] >= FUZZY_MATCH_THRESHOLD:
            return self._exact[best[0]]
        return None

    def find_mentions(self, sentence: str, self_generic: str = "") -> list[Mention]:
        """句子中所有药物提及,按出现位置排序;同一位置保留最长匹配。"""
        mentions: list[Mention] = []

        # 自指
        for ref in SELF_REFERENCES:
            start = 0
            while True:
                idx = sentence.find(ref, start)
                if idx < 0:
                    break
                if self_generic:
                    mentions.append(Mention(ref, idx, idx + len(ref), self_generic, "self"))
                start = idx + len(ref)

        # 精确匹配(长名优先)
        occupied: list[tuple[int, int]] = []
        for name in self._all_names:
            start = 0
            while True:
                idx = sentence.find(name, start)
                if idx < 0:
                    break
                end = idx + len(name)
                if not any(idx < e and s < end for s, e in occupied):
                    mentions.append(Mention(name, idx, end, self._exact[name], "exact"))
                    occupied.append((idx, end))
                start = end

        # 模糊匹配:在未被精确/自指占用的中文片段上滑窗
        occupied.sort()
        gaps = self._free_gaps(len(sentence), occupied)
        for gs, ge in gaps:
            piece = sentence[gs:ge]
            # 跳过明显不是药名的片段
            if not self._looks_drug_like(piece):
                continue
            best = self._best_fuzzy(piece)
            if best:
                name, score, rel_idx, window = best
                mentions.append(Mention(
                    window, gs + rel_idx, gs + rel_idx + len(window),
                    self._exact[name], "fuzzy",
                ))

        mentions.sort(key=lambda m: (m.start, -len(m.text)))
        # 去重:重叠时保留更长/更靠前
        result: list[Mention] = []
        for m in mentions:
            if any(m.start < r.end and r.start < m.end for r in result):
                continue
            result.append(m)
        return result

    @staticmethod
    def _free_gaps(total: int, occupied: list[tuple[int, int]]) -> list[tuple[int, int]]:
        gaps, cursor = [], 0
        for s, e in occupied:
            if s > cursor:
                gaps.append((cursor, s))
            cursor = max(cursor, e)
        if cursor < total:
            gaps.append((cursor, total))
        return gaps

    @staticmethod
    def _looks_drug_like(piece: str) -> bool:
        # 至少含一个汉字且长度合理;含常见药名后缀字,或纯字母缩写(如 SMZco)
        if not (2 <= len(piece) <= 12):
            return False
        if all(ord(c) < 128 for c in piece):
            return piece.isalnum() and len(piece) >= 3
        suffixes = "啉啶平沙坦普利洛尔芬昔康唑霉素他汀嗪胍司特仑酚铵钙钠钾酸脲碘"
        return any(ch in suffixes for ch in piece) or piece.endswith(("片", "胶囊", "注射液"))

    def _best_fuzzy(self, piece: str) -> tuple[str, int, int, str] | None:
        best = None  # (name, score, rel_idx, window)
        seen_windows: set[str] = set()
        for size in range(min(9, len(piece)), 1, -1):
            for i in range(0, len(piece) - size + 1):
                window = piece[i:i + size]
                if window in seen_windows:
                    continue
                seen_windows.add(window)
                for name in self._fuzzy_names:
                    if abs(len(name) - size) > 3:
                        continue
                    # 全串比对 + 偏序比对(名称被形近字干扰时仍可命中)
                    score = max(fuzz.ratio(window, name),
                                fuzz.partial_ratio(window, name) - 4)
                    if score >= FUZZY_MATCH_THRESHOLD and (best is None or score > best[1]):
                        best = (name, score, i, window)
            if best and best[1] >= FUZZY_MATCH_THRESHOLD + 4:
                return best
        return best


def pair_key(drug_a: str, drug_b: str) -> str:
    """无序药物对的稳定键。"""
    return "|".join(sorted([drug_a, drug_b]))
