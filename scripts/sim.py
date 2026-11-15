import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rapidfuzz import fuzz

buf = io.StringIO()
pairs = [
    ("甲蝶氨呤", "甲氨蝶呤"), ("洛赛刻", "洛赛克"), ("咪唑达仑", "咪达唑仑"),
    ("氨叶甲酸", "氨甲环酸"), ("庆霉大素", "庆大霉素"), ("庆梅素", "庆大霉素"),
]
for a, b in pairs:
    print(f"{a} vs {b}: ratio={fuzz.ratio(a, b)} partial={fuzz.partial_ratio(a, b)}", file=buf)
Path("data/processed/sim.txt").write_text(buf.getvalue(), encoding="utf-8")
print("written")
