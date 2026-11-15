"""章节切分器:把行结构文本按标准章节切开,并重建带确定偏移的全文。

输出 SectionBlock,其中 text 为章节正文;full_text 由各章节拼接而成,
正文中的字符偏移在重建全文中保持一致,供抽取与前端高亮共用。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.parser.headings import normalize_heading
from app.parser.readers import RawLine


@dataclass
class SectionBlock:
    code: str
    raw_heading: str
    text: str = ""
    order_index: int = 0
    start_offset: int = -1   # 段(含标题)在 full_text 中的起始
    end_offset: int = -1
    body_start_offset: int = -1  # 正文(标题之后)在 full_text 中的起始


@dataclass
class SegmentedDocument:
    full_text: str
    sections: list[SectionBlock] = field(default_factory=list)
    section_by_code: dict[str, SectionBlock] = field(default_factory=dict)


def _looks_like_heading(line: str) -> str:
    """返回识别出的标准章节代码,否则空串。"""
    # 标题一般不超过 40 字且没有句末标点
    if len(line) > 40:
        return ""
    if line.endswith(("。", ";", "；", ".", "!", "！")):
        return ""
    return normalize_heading(line)


def segment(lines: list[RawLine]) -> SegmentedDocument:
    blocks: list[SectionBlock] = []
    current: SectionBlock | None = None
    preamble: list[str] = []  # 第一个标准标题之前的抬头内容
    doc_title_marks = {"药品说明书", "说明书", "药品使用说明书"}

    for line in lines:
        code = _looks_like_heading(line.text)
        if code:
            # 同一标准章节重复出现时合并正文
            existing = next((b for b in blocks if b.code == code), None)
            if existing is not None:
                current = existing
                continue
            current = SectionBlock(
                code=code, raw_heading=line.text,
                order_index=len(blocks),
            )
            blocks.append(current)
        elif current is None:
            # 文档级大标题(药品说明书)不作为章节,其余抬头保留到 other
            if line.text.strip() not in doc_title_marks:
                preamble.append(line.text)
        else:
            current.text = (current.text + "\n" + line.text).strip("\n") if current.text else line.text

    # 抬头并入 other(仅当确实存在第一个标准标题之前的内容)
    if preamble:
        blocks.insert(0, SectionBlock(
            code="other", raw_heading="(文首)", text="\n".join(preamble), order_index=0,
        ))
        for i, b in enumerate(blocks):
            b.order_index = i

    # 重建全文:每段 = 原始标题 + 换行 + 正文,段间单换行
    parts: list[str] = []
    for b in blocks:
        segment = b.raw_heading + "\n" + b.text if b.text else b.raw_heading
        b.start_offset = sum(len(p) + 1 for p in parts)
        b.end_offset = b.start_offset + len(segment)
        # 正文基址 = 段起始 + 标题行 + 换行(无正文时等于段末)
        b.body_start_offset = (b.start_offset + len(b.raw_heading) + 1
                               if b.text else b.end_offset)
        parts.append(segment)
    full_text = "\n".join(parts)

    return SegmentedDocument(
        full_text=full_text,
        sections=blocks,
        section_by_code={b.code: b for b in blocks},
    )
