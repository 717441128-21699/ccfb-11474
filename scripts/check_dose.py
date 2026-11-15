"""剂量 FN/FP 分析。"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db.models import Document, DosageFact, KnowledgeItem
from app.db.session import session_scope
from app.eval.evaluator import load_gold

buf = io.StringIO()
gold = load_gold()
fn, fp = [], []
with session_scope() as session:
    docs = session.scalars(select(Document)).all()
    for doc in docs:
        g = gold[doc.doc_no]
        preds = session.scalars(
            select(DosageFact).join(KnowledgeItem,
                                    DosageFact.item_id == KnowledgeItem.id)
            .where(KnowledgeItem.document_id == doc.id)).all()
        pkeys = {(d.population, d.dose_value, d.frequency) for d in preds}
        gkeys = {(d["population"], d["dose_value"], d["frequency"]) for d in g["dosages"]}
        for x in sorted(gkeys - pkeys):
            fn.append((doc.doc_no, x))
        for x in sorted(pkeys - gkeys):
            fp.append((doc.doc_no, x))

print(f"FN {len(fn)} FP {len(fp)}", file=buf)
from collections import Counter
print("FN 人群分布:", Counter(x[1][0] for x in fn), file=buf)
print("FN 样例:", file=buf)
for x in fn[:15]:
            print("  ", x, file=buf)
print("FP 样例:", file=buf)
for x in fp[:15]:
            print("  ", x, file=buf)
Path("data/processed/dose_errors.txt").write_text(buf.getvalue(), encoding="utf-8")
print("written")
