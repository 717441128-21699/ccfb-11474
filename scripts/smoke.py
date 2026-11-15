"""快速冒烟:解析一份 docx + 一份 pdf,跑三类抽取,打印结果。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.extract.interaction import extract_interactions
from app.extract.dosage import extract_dosages
from app.extract.contraindication import extract_contraindications
from app.normalize.drug_normalizer import DrugNormalizer
from app.parser.readers import read_document
from app.parser.sectioner import segment

norm = DrugNormalizer()
for fname in ["data/raw/SMPL000001.docx", "data/raw/SMPL000007.pdf"]:
    print("=" * 70)
    print(fname)
    lines = read_document(fname)
    seg = segment(lines)
    main_name = Path(fname).stem
    ib = seg.section_by_code.get("interaction")
    if ib:
        recs = extract_interactions(ib.text, ib.start_offset, norm, seg.section_by_code["drug_name"].text.split(":")[-1].split("：")[-1].strip())
        for r in recs:
            print(f"  [相互作用] {r.drug_a} <-> {r.drug_b} | {r.severity} | {r.interaction_type} | {r.mentioned_a}/{r.mentioned_b}")
    db = seg.section_by_code.get("dosage")
    if db:
        for r in extract_dosages(db.text, db.start_offset):
            print(f"  [剂量] {r.population_label} {r.dose_value} {r.frequency_label} {r.route}")
    cb = seg.section_by_code.get("contraindication")
    if cb:
        for r in extract_contraindications(cb.text, cb.start_offset):
            print(f"  [禁忌] {r.category}: {r.subject}")
