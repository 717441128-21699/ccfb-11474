"""校验所有知识条目的出处偏移:full_text[start:end] 是否等于 source_text。"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.db.models import Document, KnowledgeItem
from app.db.session import session_scope

buf = io.StringIO()
ok, bad = 0, 0
bad_samples = []
with session_scope() as session:
    docs = {d.id: d for d in session.scalars(select(Document)).all()}
    items = session.scalars(select(KnowledgeItem)).all()
    for it in items:
        d = docs[it.document_id]
        if it.source_start < 0:
            continue
        sliced = d.full_text[it.source_start:it.source_end]
        if sliced == it.source_text:
            ok += 1
        else:
            bad += 1
            if len(bad_samples) < 5:
                bad_samples.append((d.doc_no, it.id,
                                    repr(sliced[:40]), repr(it.source_text[:40])))
print(f"偏移校验通过 {ok} 条,失败 {bad} 条", file=buf)
for s in bad_samples:
    print(" BAD", s, file=buf)
Path("data/processed/offset_check.txt").write_text(buf.getvalue(), encoding="utf-8")
print("written")
