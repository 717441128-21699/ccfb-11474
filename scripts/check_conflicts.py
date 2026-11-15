"""冲突表诊断。"""
import io
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, func

from app.db.models import Conflict, InteractionFact, KnowledgeItem, Document
from app.db.session import session_scope

buf = io.StringIO()
with session_scope() as session:
    total = session.scalar(select(func.count()).select_from(Conflict))
    print("冲突总数:", total, file=buf)
    rows = session.scalars(select(Conflict)).all()
    print("类型分布:", Counter(r.conflict_type for r in rows), file=buf)
    pair_counter = Counter(r.pair_key for r in rows)
    print("出现冲突最多的 pair:", pair_counter.most_common(8), file=buf)
    # 一个 pair 在多少文档出现
    facts = session.scalars(
        select(InteractionFact).join(KnowledgeItem,
                                     InteractionFact.item_id == KnowledgeItem.id)).all()
    pair_docs: dict[str, set] = {}
    items = {it.id: it for it in session.scalars(select(KnowledgeItem)).all()}
    for f in facts:
        pair_docs.setdefault(f.pair_key, set()).add(items[f.item_id].document_id)
    sizes = Counter(len(v) for v in pair_docs.values())
    print("每个 pair 的文档数分布:", dict(sorted(sizes.items())), file=buf)
    for r in rows[:8]:
        print(" ", r.pair_key, r.conflict_type, r.doc_no_1, r.doc_no_2, r.detail, file=buf)
Path("data/processed/conflict_check.txt").write_text(buf.getvalue(), encoding="utf-8")
print("written")
