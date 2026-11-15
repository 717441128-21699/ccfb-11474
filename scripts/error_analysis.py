"""错误分析:把 FN/FP、严重程度错判、类型错判样例写到 UTF-8 文件。"""
import io
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db.models import Document, InteractionFact, KnowledgeItem
from app.db.session import session_scope
from app.eval.evaluator import load_gold

buf = io.StringIO()
gold = load_gold()
fn_samples, fp_samples, sev_err, type_err = [], [], [], []

with session_scope() as session:
    docs = session.scalars(select(Document)).all()
    for doc in docs:
        g = gold[doc.doc_no]
        preds = session.scalars(
            select(InteractionFact).join(KnowledgeItem,
                                         InteractionFact.item_id == KnowledgeItem.id)
            .where(KnowledgeItem.document_id == doc.id)).all()
        pred_by_pair: dict[str, list[InteractionFact]] = {}
        for p in preds:
            pred_by_pair.setdefault(p.pair_key, []).append(p)
        gold_by_pair: dict[str, dict] = {}
        for x in g["interactions"]:
            gold_by_pair.setdefault(x["pair_key"], x)

        for key, gx in gold_by_pair.items():
            cands = pred_by_pair.get(key)
            if not cands:
                fn_samples.append((doc.doc_no, gx["sentence"]))
            else:
                if not any(c.severity == gx["severity"] for c in cands):
                    sev_err.append((doc.doc_no, gx["severity"],
                                    "/".join(sorted({c.severity for c in cands})),
                                    gx["sentence"]))
                if not any(c.severity == gx["severity"]
                           and c.interaction_type == gx["interaction_type"]
                           for c in cands):
                    type_err.append((doc.doc_no, gx["interaction_type"],
                                     "/".join(sorted({c.interaction_type for c in cands})),
                                     gx["sentence"]))
        for key, cands in pred_by_pair.items():
            if key not in gold_by_pair:
                fp_samples.append((doc.doc_no, key,
                                   cands[0].effect_desc[:80]))

print(f"FN 总数: {len(fn_samples)}", file=buf)
print("FN 样例(前25):", file=buf)
for x in fn_samples[:25]:
    print("  ", x, file=buf)
print(f"\nFP 总数: {len(fp_samples)}", file=buf)
print("FP 样例(前25):", file=buf)
for x in fp_samples[:25]:
    print("  ", x, file=buf)
print(f"\n严重程度错判: {len(sev_err)}", file=buf)
conf = Counter((g, p) for _, g, p, _ in sev_err)
for k, v in conf.most_common(12):
    print(f"  gold={k[0]} -> pred={k[1]}: {v}", file=buf)
for x in sev_err[:10]:
    print("   ", x, file=buf)
print(f"\n类型错判: {len(type_err)}", file=buf)
conf2 = Counter((g, p) for _, g, p, _ in type_err)
for k, v in conf2.most_common(15):
    print(f"  gold={k[0]} -> pred={k[1]}: {v}", file=buf)
for x in type_err[:10]:
    print("   ", x, file=buf)

Path("data/processed/error_analysis.txt").write_text(buf.getvalue(), encoding="utf-8")
print("written")
