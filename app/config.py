"""全局配置:路径、数据库、抽取阈值等集中管理。"""
from __future__ import annotations

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"          # 原始说明书 docx/pdf
PROCESSED_DIR = DATA_DIR / "processed"  # 解析出的纯文本(便于排查)
DB_DIR = DATA_DIR / "db"
EXPORT_DIR = DATA_DIR / "export"
GOLD_DIR = DATA_DIR / "gold"         # 人工标注(模拟)
for _d in (RAW_DIR, PROCESSED_DIR, DB_DIR, EXPORT_DIR, GOLD_DIR):
    _d.mkdir(parents=True, exist_ok=True)

DB_PATH = DB_DIR / "drug_kb.sqlite3"
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

# RapidFuzz 药名容错匹配阈值(0-100)
FUZZY_MATCH_THRESHOLD = 88

# 评估目标
TARGET_PRECISION = 0.90
TARGET_RECALL = 0.90

# 标准章节定义(代码 -> 中文名)
STANDARD_SECTIONS = {
    "drug_name": "药品名称",
    "ingredient": "成份",
    "description": "性状",
    "indication": "适应症",
    "contraindication": "禁忌",
    "dosage": "用法用量",
    "adverse_reaction": "不良反应",
    "precaution": "注意事项",
    "pregnancy": "孕妇及哺乳期妇女用药",
    "pediatric": "儿童用药",
    "geriatric": "老年用药",
    "interaction": "药物相互作用",
    "overdose": "药物过量",
    "pharmacology": "药理毒理",
    "pharmacokinetics": "药代动力学",
    "storage": "贮藏",
    "packaging": "包装",
    "validity": "有效期",
    "approval": "批准文号",
    "manufacturer": "生产企业",
    "other": "其他",
}
