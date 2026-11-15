import io
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.parser.readers import read_document
from app.parser.sectioner import segment

buf = io.StringIO()
seg = segment(read_document("data/raw/SMPL000001.docx"))
for b in seg.sections[:4]:
    print(b.code, repr(b.raw_heading), repr(b.text[:40]), file=buf)
# 统计 500 份里 other 的来源
cnt = Counter()
for fp in sorted(Path("data/raw").glob("SMPL*.*"))[:50]:
    s = segment(read_document(fp))
    for b in s.sections:
        if b.code == "other":
            cnt[b.raw_heading] += 1
print("other 来源:", cnt, file=buf)
Path("data/processed/section_debug.txt").write_text(buf.getvalue(), encoding="utf-8")
print("written")
