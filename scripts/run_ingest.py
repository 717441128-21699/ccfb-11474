"""批量入库:把 data/raw 下全部说明书经流水线写入 SQLite。

用法: py -I scripts/run_ingest.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete

from app.db.models import Conflict
from app.db.session import init_db, session_scope
from app.extract.conflicts import detect_conflicts
from app.extract.pipeline import ingest_file
from app.config import GOLD_DIR, RAW_DIR


def main() -> None:
    init_db()
    manifest = {x["doc_no"]: x for x in
                json.loads((GOLD_DIR / "manifest.json").read_text(encoding="utf-8"))["items"]} \
        if (GOLD_DIR / "manifest.json").exists() else {}
    # manifest.json 结构为 {count, seed, ...} 时改用 gold jsonl 兜底
    if not manifest:
        for line in (GOLD_DIR / "gold_annotations.jsonl").read_text(encoding="utf-8").splitlines():
            meta = json.loads(line)
            manifest[meta["doc_no"]] = meta

    files = sorted(RAW_DIR.glob("SMPL*.*"))
    totals = {"sections": 0, "interactions": 0, "dosages": 0,
              "contraindications": 0, "conflicts_added": 0}
    with session_scope() as session:
        for fp in files:
            doc_no = fp.stem
            meta = manifest.get(doc_no, {})
            res = ingest_file(
                session, fp, doc_no=doc_no,
                generic_name=meta.get("generic_name", ""),
                manufacturer=meta.get("manufacturer", ""),
                approval_no=meta.get("approval_no", ""),
                style_family=meta.get("style_family", ""),
            )
            for k in ("sections", "interactions", "dosages", "contraindications"):
                totals[k] += getattr(res, k)
        # 全库冲突只在所有文档入库后计算一次
        session.execute(delete(Conflict))
        conflicts = detect_conflicts(session)
        totals["conflicts_added"] = len(conflicts)
    print(f"入库 {len(files)} 份: {totals}")


if __name__ == "__main__":
    main()
