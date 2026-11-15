"""SQLAlchemy 数据模型。

覆盖:说明书文档、标准章节、药名词典、知识条目(相互作用/剂量/禁忌)、
冲突、审核记录、导出日志。
"""
from __future__ import annotations

import datetime as _dt
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


class Base(DeclarativeBase):
    pass


class Document(Base):
    """一份说明书文件。"""
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    file_path: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(10))          # docx / pdf
    doc_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)  # 院内编号
    title: Mapped[str] = mapped_column(String(200), default="")
    generic_name: Mapped[str] = mapped_column(String(100), default="", index=True)
    manufacturer: Mapped[str] = mapped_column(String(200), default="")
    approval_no: Mapped[str] = mapped_column(String(60), default="")
    full_text: Mapped[str] = mapped_column(Text, default="")
    style_family: Mapped[str] = mapped_column(String(40), default="")  # 标题风格族
    created_at: Mapped[str] = mapped_column(String(30), default=_now)

    sections: Mapped[list["Section"]] = relationship(
        back_populates="document", cascade="all, delete-orphan",
        order_by="Section.order_index",
    )
    items: Mapped[list["KnowledgeItem"]] = relationship(
        back_populates="document", cascade="all, delete-orphan",
    )


class Section(Base):
    """标准化后的章节(切片结果)。"""
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    code: Mapped[str] = mapped_column(String(30), index=True)       # 标准章节代码
    raw_heading: Mapped[str] = mapped_column(String(200), default="")  # 原文标题
    text: Mapped[str] = mapped_column(Text, default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    document: Mapped[Document] = relationship(back_populates="sections")


class DrugEntity(Base):
    """药名词典:一个通用名一条,商品名/别名以逗号挂接。"""
    __tablename__ = "drug_entities"

    id: Mapped[int] = mapped_column(primary_key=True)
    generic_name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    trade_names: Mapped[str] = mapped_column(Text, default="")   # 逗号分隔
    aliases: Mapped[str] = mapped_column(Text, default="")
    atc_category: Mapped[str] = mapped_column(String(40), default="")

    def all_names(self) -> list[str]:
        names = [self.generic_name]
        names.extend(x for x in self.trade_names.split(",") if x)
        names.extend(x for x in self.aliases.split(",") if x)
        return names


class KnowledgeItem(Base):
    """抽取明细的统一主表,具体字段落在子表。"""
    __tablename__ = "knowledge_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    item_type: Mapped[str] = mapped_column(String(20), index=True)  # interaction/dosage/contraindication
    section_code: Mapped[str] = mapped_column(String(30), default="")
    # 出处:章节文本中的字符区间 [start,end),前端据此高亮
    source_text: Mapped[str] = mapped_column(Text, default="")
    source_start: Mapped[int] = mapped_column(Integer, default=-1)
    source_end: Mapped[int] = mapped_column(Integer, default=-1)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # 审核状态:pending / approved / rejected
    review_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    reviewer: Mapped[str] = mapped_column(String(60), default="")
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_at: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    created_at: Mapped[str] = mapped_column(String(30), default=_now)

    document: Mapped[Document] = relationship(back_populates="items")
    interaction: Mapped[Optional["InteractionFact"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", uselist=False)
    dosage: Mapped[Optional["DosageFact"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", uselist=False)
    contraindication: Mapped[Optional["ContraindicationFact"]] = relationship(
        back_populates="item", cascade="all, delete-orphan", uselist=False)


class InteractionFact(Base):
    """药物相互作用:药物对 + 作用类型 + 严重程度。"""
    __tablename__ = "interaction_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("knowledge_items.id"), unique=True)
    drug_a: Mapped[str] = mapped_column(String(100), index=True)   # 统一为通用名
    drug_b: Mapped[str] = mapped_column(String(100), index=True)
    pair_key: Mapped[str] = mapped_column(String(220), index=True)  # 排序后的无序对
    interaction_type: Mapped[str] = mapped_column(String(40), default="")
    severity: Mapped[str] = mapped_column(String(20), default="")  # 禁忌/高/中/低
    effect_desc: Mapped[str] = mapped_column(Text, default="")
    # 原文中实际出现的药名(可能是商品名/别名),供溯源核对
    mentioned_a: Mapped[str] = mapped_column(String(100), default="")
    mentioned_b: Mapped[str] = mapped_column(String(100), default="")

    item: Mapped[KnowledgeItem] = relationship(back_populates="interaction")


class DosageFact(Base):
    """剂量:人群分开,用量与频次拆字段。"""
    __tablename__ = "dosage_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("knowledge_items.id"), unique=True)
    population: Mapped[str] = mapped_column(String(20), index=True)  # adult/child/renal/hepatic/elderly
    population_label: Mapped[str] = mapped_column(String(60), default="")
    dose_value: Mapped[str] = mapped_column(String(60), default="")   # 保留原文数值+单位
    dose_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dose_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dose_unit: Mapped[str] = mapped_column(String(20), default="")
    frequency: Mapped[str] = mapped_column(String(40), default="")   # 标准化频次码
    frequency_label: Mapped[str] = mapped_column(String(60), default="")
    route: Mapped[str] = mapped_column(String(40), default="")       # 给药途径
    duration: Mapped[str] = mapped_column(String(60), default="")

    item: Mapped[KnowledgeItem] = relationship(back_populates="dosage")


class ContraindicationFact(Base):
    """禁忌条目(人群/疾病/药物禁忌)。"""
    __tablename__ = "contraindication_facts"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("knowledge_items.id"), unique=True)
    subject: Mapped[str] = mapped_column(String(200), default="")  # 禁忌对象
    category: Mapped[str] = mapped_column(String(30), default="")  # population/disease/drug/other

    item: Mapped[KnowledgeItem] = relationship(back_populates="contraindication")


class Conflict(Base):
    """两份说明书对同一药物对的矛盾说法。"""
    __tablename__ = "conflicts"

    id: Mapped[int] = mapped_column(primary_key=True)
    pair_key: Mapped[str] = mapped_column(String(220), index=True)
    drug_a: Mapped[str] = mapped_column(String(100))
    drug_b: Mapped[str] = mapped_column(String(100))
    conflict_type: Mapped[str] = mapped_column(String(30))
    # severity_mismatch / effect_mismatch / contra_vs_non
    item_id_1: Mapped[int] = mapped_column(ForeignKey("knowledge_items.id"))
    item_id_2: Mapped[int] = mapped_column(ForeignKey("knowledge_items.id"))
    doc_no_1: Mapped[str] = mapped_column(String(40))
    doc_no_2: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text, default="")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[str] = mapped_column(String(30), default=_now)


class ExportLog(Base):
    """审方系统导出日志。"""
    __tablename__ = "export_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    export_path: Mapped[str] = mapped_column(String(500))
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(30), default=_now)
