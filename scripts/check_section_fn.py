import io
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.parser.readers import read_document
from app.parser.sectioner import segment
from app.eval.evaluator import STYLE_SECTION_CODES

buf = io.StringIO()
missing = Counter()
missing_by_type = Counter()
examples = []
for fp in sorted(Path("data/raw").glob("SMPL*.*")):
    seg = segment(read_document(fp))
    codes = {b.code for b in seg.sections}
    miss = set(STYLE_SECTION_CODES) - codes
    for m in miss:
        missing[m] += 1
        missing_by_type[fp.suffix] += 1
    if miss and len(examples) < 10:
        examples.append((fp.name, miss, [b.raw_heading for b in seg.sections][:5]))
print("缺失章节分布:", dict(missing), file=buf)
print("缺失按文件类型:", dict(missing_by_type), file=buf)
for e in examples:
    print(e, file=buf)
Path("data/processed/section_fn.txt").write_text(buf.getvalue(), encoding="utf-8")
print("written")
