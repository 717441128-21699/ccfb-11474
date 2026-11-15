"""评估入口:跑全量 P/R,报告写 data/processed/eval_report.json 并打印摘要。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import PROCESSED_DIR
from app.db.session import session_scope
from app.eval.evaluator import evaluate


def main() -> None:
    with session_scope() as session:
        report = evaluate(session)
    out = PROCESSED_DIR / "eval_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"评估文档数: {report['docs']}", ""]
    lines.append(f"{'指标':<28}{'TP':>6}{'FP':>6}{'FN':>6}{'P':>9}{'R':>9}{'F1':>9}")
    for m in report["metrics"]:
        lines.append(
            f"{m['name']:<28}{m['tp']:>6}{m['fp']:>6}{m['fn']:>6}"
            f"{m['precision']:>9.4f}{m['recall']:>9.4f}{m['f1']:>9.4f}")
    lines.append("")
    for k, v in report["targets_met"].items():
        lines.append(f"[{'达标' if v else '未达'}] {k}")
    text = "\n".join(lines)
    (PROCESSED_DIR / "eval_report.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
