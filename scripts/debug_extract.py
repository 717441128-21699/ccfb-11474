"""调试:把切分/抽取结果以 UTF-8 写文件,绕过控制台编码。"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extract.interaction import extract_interactions
from app.normalize.drug_normalizer import DrugNormalizer
from app.parser.readers import read_document
from app.parser.sectioner import segment

out = io.StringIO()
norm = DrugNormalizer()
for fname in ["data/raw/SMPL000001.docx", "data/raw/SMPL000007.pdf"]:
    print("=" * 70, file=out)
    print(fname, file=out)
    lines = read_document(fname)
    seg = segment(lines)
    ib = seg.section_by_code.get("interaction")
    print("--- 相互作用章节原文 ---", file=out)
    print(ib.text, file=out)
    self_name = seg.section_by_code["drug_name"].text.splitlines()[0].split("：")[-1].split(":")[-1].strip()
    print(f"自指通用名: {self_name}", file=out)
    recs = extract_interactions(ib.text, ib.start_offset, norm, self_name)
    print(f"--- 抽取 {len(recs)} 条 ---", file=out)
    for r in recs:
        print(f"{r.drug_a} <-> {r.drug_b} | {r.severity} | {r.interaction_type} | 提及:{r.mentioned_a}/{r.mentioned_b}", file=out)

Path("data/processed/debug.txt").write_text(out.getvalue(), encoding="utf-8")
print("written")
