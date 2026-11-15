import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.extract.conflicts import _judge

f = lambda s, t: SimpleNamespace(severity=s, interaction_type=t)
out = []
out.append(f"禁忌/低 -> {_judge(f('禁忌', '酶抑制'), f('低', '其他'))}")
out.append(f"禁忌/中 -> {_judge(f('禁忌', '酶抑制'), f('中', '其他'))}")
out.append(f"高/低 -> {_judge(f('高', '出血风险'), f('低', '出血风险'))}")
Path("data/processed/judge_check.txt").write_text("\n".join(out), encoding="utf-8")
print("written")
