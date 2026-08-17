"""关键词初筛规则（keyword_rules 表）：可配置化，M1 建表，M2 填充启用。"""
from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class KeywordRule(Base):
    __tablename__ = "keyword_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    pattern: Mapped[str] = mapped_column(String(255))  # 关键词/正则
    field: Mapped[str] = mapped_column(String(16), default="any")  # title/abstract/any
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<KeywordRule {self.pattern} ({self.field})>"
