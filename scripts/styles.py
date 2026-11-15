"""章节标题风格族:同一标准章节在不同药厂说明书中的不同写法。

四个风格族覆盖:国标【】式、中文编号式、阿拉伯数字式、无编号近义式。
"""
from __future__ import annotations

# 风格族 -> 标准代码 -> 标题渲染
STYLE_FAMILIES = {
    "gb_bracket": {  # 国标说明书风格【药物相互作用】
        "drug_name": "【药品名称】", "ingredient": "【成份】", "description": "【性状】",
        "indication": "【适应症】", "contraindication": "【禁忌】", "dosage": "【用法用量】",
        "adverse_reaction": "【不良反应】", "precaution": "【注意事项】",
        "pregnancy": "【孕妇及哺乳期妇女用药】", "pediatric": "【儿童用药】",
        "geriatric": "【老年用药】", "interaction": "【药物相互作用】",
        "overdose": "【药物过量】", "pharmacology": "【药理毒理】",
        "pharmacokinetics": "【药代动力学】", "storage": "【贮藏】",
        "packaging": "【包装】", "validity": "【有效期】",
        "approval": "【批准文号】", "manufacturer": "【生产企业】",
    },
    "cn_number": {  # 一、药物相互作用
        "drug_name": "一、药品名称", "ingredient": "二、成份", "description": "三、性状",
        "indication": "四、适应症", "contraindication": "五、禁忌",
        "dosage": "六、用法用量", "adverse_reaction": "七、不良反应",
        "precaution": "八、注意事项", "pregnancy": "九、孕妇及哺乳期妇女用药",
        "pediatric": "十、儿童用药", "geriatric": "十一、老年用药",
        "interaction": "十二、药物相互作用", "overdose": "十三、药物过量",
        "pharmacology": "十四、药理毒理", "pharmacokinetics": "十五、药代动力学",
        "storage": "十六、贮藏", "packaging": "十七、包装", "validity": "十八、有效期",
        "approval": "十九、批准文号", "manufacturer": "二十、生产企业",
    },
    "arabic_number": {  # 1. 药物交互作用(近义替换)
        "drug_name": "1. 通用名称", "ingredient": "2. 主要成分", "description": "3. 外观性状",
        "indication": "4. 适应证", "contraindication": "5. 禁忌症",
        "dosage": "6. 用法与用量", "adverse_reaction": "7. 药物不良反应",
        "precaution": "8. 用药须知", "pregnancy": "9. 妊娠期及哺乳期用药",
        "pediatric": "10. 小儿用药", "geriatric": "11. 老年患者用药",
        "interaction": "12. 药物交互作用", "overdose": "13. 用药过量",
        "pharmacology": "14. 药理作用", "pharmacokinetics": "15. 药物代谢动力学",
        "storage": "16. 储存条件", "packaging": "17. 药品包装",
        "validity": "18. 有效期限", "approval": "19. 注册证号",
        "manufacturer": "20. 生产厂家",
    },
    "plain_alt": {  # 无编号,近义标题
        "drug_name": "药品名称", "ingredient": "活性成份", "description": "性状",
        "indication": "功能主治", "contraindication": "禁用范围",
        "dosage": "给药途径及用量", "adverse_reaction": "副作用",
        "precaution": "警告和注意事项", "pregnancy": "孕哺期用药",
        "pediatric": "儿科用药", "geriatric": "老年人群用药",
        "interaction": "与其他药物的相互作用", "overdose": "过量处理",
        "pharmacology": "药理作用及毒理", "pharmacokinetics": "体内过程",
        "storage": "保存方法", "packaging": "包装规格", "validity": "保质期",
        "approval": "国药准字", "manufacturer": "上市许可持有人",
    },
}

MANUFACTURERS = [
    "华北制药股份有限公司", "扬子江药业集团有限公司", "齐鲁制药有限公司",
    "石药集团欧意药业有限公司", "正大天晴药业集团股份有限公司",
    "江苏恒瑞医药股份有限公司", "华东医药股份有限公司", "云南白药集团股份有限公司",
    "北京双鹭药业股份有限公司", "上海医药集团股份有限公司", "广州白云山医药集团",
    "成都倍特药业股份有限公司",
]
