import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.extract import conflicts as C

f1 = SimpleNamespace(severity="禁忌", interaction_type="酶抑制")
f2 = SimpleNamespace(severity="低", interaction_type="其他")
out = []
out.append(f"f1.severity={f1.severity!r} f2.severity={f2.severity!r}")
out.append(f"tuple=({f1.severity}, {f2.severity})")
out.append(f"禁忌 in tuple: {'禁忌' in (f1.severity, f2.severity)}")
out.append(f"禁忌 not in tuple: {'禁忌' not in (f1.severity, f2.severity)}")
out.append(f"SEV_ORDER={C.SEV_ORDER}")
out.append(f"judge result: {C._judge(f1, f2)}")
Path("data/processed/judge_debug.txt").write_text("\n".join(out), encoding="utf-8")
print("written")
