"""说明书文件读取:docx / pdf -> 带行结构的纯文本。

统一输出 list[RawLine],保留换行,章节切分器据此识别标题。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RawLine:
    text: str
    line_no: int


def read_docx(path: str | Path) -> list[RawLine]:
    from docx import Document as DocxDocument

    doc = DocxDocument(str(path))
    lines: list[RawLine] = []
    n = 0
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            n += 1
            lines.append(RawLine(text=text, line_no=n))
    # 表格里的文字也收进来(部分说明书把相互作用放在表格中)
    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                n += 1
                lines.append(RawLine(text=" ".join(cells), line_no=n))
    return lines


def read_pdf(path: str | Path) -> list[RawLine]:
    import pdfplumber

    lines: list[RawLine] = []
    n = 0
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            for raw in text.splitlines():
                text_line = raw.strip()
                if text_line:
                    n += 1
                    lines.append(RawLine(text=text_line, line_no=n))
    return lines


def read_document(path: str | Path) -> list[RawLine]:
    suffix = Path(path).suffix.lower()
    if suffix == ".docx":
        return read_docx(path)
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix == ".txt":
        lines: list[RawLine] = []
        for i, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                lines.append(RawLine(text=line.strip(), line_no=i))
        return lines
    raise ValueError(f"不支持的文件类型: {suffix}")


def lines_to_text(lines: list[RawLine]) -> str:
    return "\n".join(x.text for x in lines)
