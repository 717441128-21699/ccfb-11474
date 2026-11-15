import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extract.dosage import extract_dosages
from app.extract.sentences import split_sentences
from app.parser.readers import read_document
from app.parser.sectioner import segment

buf = io.StringIO()
lines = read_document("data/raw/SMPL000001.docx")
seg = segment(lines)
ped = seg.section_by_code.get("pediatric")
dose = seg.section_by_code.get("dosage")
print("儿童章节文本:", repr(ped.text), file=buf)
print("儿童章节句子:", [(s.text, s.start, s.end) for s in split_sentences(ped.text)], file=buf)
recs = extract_dosages(dose.text, dose.start_offset,
                       [(ped.text, ped.start_offset)])
for r in recs:
    print(r.population, r.dose_value, r.frequency, r.route, file=buf)
Path("data/processed/dose_debug.txt").write_text(buf.getvalue(), encoding="utf-8")
print("written")
