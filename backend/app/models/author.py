"""作者（authors 表）：v1 仅做小写/去点归一，同名歧义不处理。"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    name_normalized: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    paper_links: Mapped[list["PaperAuthor"]] = relationship(back_populates="author")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Author {self.name}>"
