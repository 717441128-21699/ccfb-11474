"""统计错别字句的抽取情况,并测试模糊匹配对各扰动的命中率。"""
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.normalize.drug_normalizer import DrugNormalizer

norm = DrugNormalizer()
buf = io.StringIO()

# 1) 直接测常见扰动名能否归一
tests = ["呋米", "地辛", "甲蝶氨呤", "洛克", "氨叶酸", "泰能", "美多心安",
         "可达龙", "波立维", "络活喜", "新诺明", "里素劳", "异丁苯丙酸",
         "甲哌利福霉素", "倍他乐克", "阿乐", "立普妥", "奇曼丁", "西普乐"]
for t in tests:
    print(f"{t} -> {norm.normalize(t)}", file=buf)

# 2) gold 中含扰动的句子及其期望药名
gold = [json.loads(x) for x in
        Path("data/gold/gold_annotations.jsonl").read_text(encoding="utf-8").splitlines()]
typo_hits, typo_miss = 0, 0
miss_examples = []
for g in gold:
    for inter in g["interactions"]:
        sent = inter["sentence"]
        mentions = norm.find_mentions(sent, self_generic=g["generic_name"])
        names = {m.generic_name for m in mentions}
        if inter["drug_a"] not in names or inter["drug_b"] not in names:
            # 只统计名称层面失败的
            typo_miss += 1
            if len(miss_examples) < 20:
                miss_examples.append((g["doc_no"], inter["drug_a"], inter["drug_b"],
                                      sent, sorted(names)))
        else:
            typo_hits += 1
print(f"\n药物提及成功 {typo_hits}, 失败 {typo_miss}", file=buf)
for x in miss_examples:
            print("  MISS", x, file=buf)

Path("data/processed/fuzzy_check.txt").write_text(buf.getvalue(), encoding="utf-8")
print("written")
