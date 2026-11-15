"""把 data/drug_dictionary.json 写入 drug_entities 表(幂等)。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.config import ROOT_DIR
from app.db.models import DrugEntity
from app.db.session import init_db, session_scope


def main() -> None:
    init_db()
    data = json.loads((ROOT_DIR / "data" / "drug_dictionary.json").read_text("utf-8"))
    with session_scope() as session:
        existing = {d.generic_name for d in session.scalars(select(DrugEntity)).all()}
        n = 0
        for ent in data:
            if ent["generic_name"] in existing:
                continue
            session.add(DrugEntity(
                generic_name=ent["generic_name"],
                trade_names=",".join(ent.get("trade_names", [])),
                aliases=",".join(ent.get("aliases", [])),
                atc_category=ent.get("atc_category", ""),
            ))
            n += 1
    print(f"药名词典入库 {n} 条(共 {len(data)} 个通用名)")


if __name__ == "__main__":
    main()
