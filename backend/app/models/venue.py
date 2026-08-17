"""会议/期刊（venues 表）：CCF 名单是数据不是代码。"""
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(primary_key=True)
    short_name: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # 如 ICSE
    full_name: Mapped[str] = mapped_column(String(255))  # 如 International Conference on Software Engineering
    type: Mapped[str] = mapped_column(String(16), default="conference")  # conference/journal
    rank: Mapped[str] = mapped_column(String(8), default="A")  # CCF-A/B/C/none
    dblp_key: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)  # 如 conf/icse
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    papers: Mapped[list["Paper"]] = relationship(back_populates="venue")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Venue {self.short_name} ({self.rank})>"
