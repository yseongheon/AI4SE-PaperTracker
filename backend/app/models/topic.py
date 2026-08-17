"""主题（topics 表）+ 论文-主题关联表。

主题分类法是数据驱动：初版 10 主题，增删改只动数据不改代码。
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # 如 code_repair
    name_zh: Mapped[str] = mapped_column(String(64))  # 如 代码修复
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    paper_links: Mapped[list["PaperTopic"]] = relationship(back_populates="topic")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Topic {self.slug}>"


class PaperTopic(Base):
    """论文-主题多标签关联：置信度 + 标注来源（keyword/llm），可追溯。"""

    __tablename__ = "paper_topics"

    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), primary_key=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    method: Mapped[str] = mapped_column(String(16), default="keyword")  # keyword/llm
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    paper: Mapped["Paper"] = relationship(back_populates="topic_links")  # noqa: F821
    topic: Mapped[Topic] = relationship(back_populates="paper_links")
