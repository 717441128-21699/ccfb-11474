"""句子切分:按中文句末标点切分,保留每句在章节正文中的字符偏移。"""
from __future__ import annotations

from dataclasses import dataclass

# 句末标点(;；也作为分隔,相互作用章节常用分号列举)
_END_MARKS = "。;；!！?？"
# 顿号/逗号不分句,但列表型短句用分号已足够


@dataclass
class Sentence:
    text: str
    start: int   # 在章节正文中的偏移
    end: int


def split_sentences(section_text: str) -> list[Sentence]:
    sentences: list[Sentence] = []
    buf: list[str] = []
    seg_start = 0
    for i, ch in enumerate(section_text):
        buf.append(ch)
        if ch in _END_MARKS or ch == "\n":
            text = "".join(buf).strip()
            if text:
                # 重新定位 strip 后的真实起点
                lead = len("".join(buf)) - len("".join(buf).lstrip())
                sentences.append(Sentence(
                    text=text,
                    start=seg_start + lead,
                    end=seg_start + len("".join(buf)),
                ))
            buf = []
            seg_start = i + 1
    tail = "".join(buf).strip()
    if tail:
        lead = len("".join(buf)) - len("".join(buf).lstrip())
        sentences.append(Sentence(
            text=tail, start=seg_start + lead, end=seg_start + len("".join(buf)),
        ))
    return sentences
