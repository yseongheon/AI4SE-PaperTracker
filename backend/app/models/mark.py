"""个性化阅读标记（user_marks 表，M6）：收藏 / 已读 / 稍后读。

单用户无认证体系，标记直接挂在论文上；复合主键 (paper_id, mark_type) 幂等。
"""
import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MarkType(str, enum.Enum):
    """阅读标记类型：bookmark 收藏 / read 已读 / read_later 稍后读。"""

    BOOKMARK = "bookmark"
    READ = "read"
    READ_LATER = "read_later"


class UserMark(Base):
    __tablename__ = "user_marks"

    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    mark_type: Mapped[str] = mapped_column(String(16), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    paper: Mapped["Paper"] = relationship()  # noqa: F821

    def __repr__(self) -> str:
        return f"<UserMark {self.paper_id} {self.mark_type}>"
