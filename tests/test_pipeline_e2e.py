"""端到端:生成一份 docx -> 切章节 -> 入库 -> 抽取 -> 偏移校验。"""
from docx import Document as DocxDocument

from app.db.models import Document, KnowledgeItem
from app.db.session import init_db, session_scope
from app.extract.pipeline import ingest_file


def _make_docx(path):
    doc = DocxDocument()
    doc.add_heading("药品说明书", level=1)
    for heading, body in [
        ("【药品名称】", "通用名称:华法林钠\n商品名称:可密定"),
        ("【适应症】", "用于血栓栓塞性疾病的防治。"),
        ("【禁忌】", "以下情况禁用:\n活动性消化性溃疡患者禁用。\n孕妇及哺乳期妇女禁用。"),
        ("【用法用量】", "成人推荐剂量为10mg,口服,每日1次。"),
        ("【儿童用药】", "儿童按体重给药,5mg/kg,每日2次。"),
        ("【药物相互作用】",
         "华法林钠与阿司匹林合用,可显著增加出血的风险。\n"
         "华法林钠与胺碘酮合用,禁止联合使用,可引起出血。\n"
         "本品的药物相互作用研究数据有限。"),
        ("【贮藏】", "遮光,密封保存。"),
    ]:
        doc.add_paragraph(heading)
        for line in body.split("\n"):
            doc.add_paragraph(line)
    doc.save(str(path))


def test_end_to_end(tmp_path):
    init_db()
    fp = tmp_path / "T.docx"
    _make_docx(fp)
    with session_scope() as session:
        res = ingest_file(session, fp, doc_no="UT001",
                          generic_name="华法林钠", manufacturer="测试厂")
        assert res.interactions == 2          # 干扰句不产生条目
        assert res.dosages >= 2               # 成人 + 儿童
        assert res.contraindications >= 2

        doc = session.query(Document).filter_by(doc_no="UT001").one()
        # 偏移精确可切回原句
        for item in session.query(KnowledgeItem).filter_by(document_id=doc.id):
            assert doc.full_text[item.source_start:item.source_end] == item.source_text
