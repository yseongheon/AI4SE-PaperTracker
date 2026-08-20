"""论文（papers 表，核心表）+ 论文-作者关联表。

设计要点（见 CLAUDE.md 第 5 章）：
- arxiv_id / dblp_key 唯一索引 → 双源幂等 upsert
- title_normalized 标题指纹 → 预印本↔正式版跨源匹配
- 同一论文的 arXiv 预印本与会议正式版是同一条记录（回填 venue/dblp_key/doi，双链接展示）
- 时间字段统一存 naive UTC（SQLite 无时区），展示层转本地
"""
import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class MatchStatus(str, enum.Enum):
    """DBLP 匹配状态：none 未匹配 / matched 已关联 / pending 歧义待复核 / rejected 确认无正式版。"""

    NONE = "none"
    MATCHED = "matched"
    PENDING = "pending"
    REJECTED = "rejected"


class PaperStatus(str, enum.Enum):
    """论文在管线中的阶段：fetched 已抓取 / matched 已 A 会匹配 / classified 已分类 / ready 全部完成。"""

    FETCHED = "fetched"
    MATCHED = "matched"
    CLASSIFIED = "classified"
    READY = "ready"


class Paper(Base):
    __tablename__ = "papers"
    __table_args__ = (
        Index("ix_papers_venue_year", "venue_id", "year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    title_normalized: Mapped[str] = mapped_column(Text, index=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    arxiv_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)  # 如 2502.12345
    arxiv_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dblp_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)  # 如 conf/icse/xxx
    doi: Mapped[str | None] = mapped_column(String(128), nullable=True)
    venue_id: Mapped[int | None] = mapped_column(ForeignKey("venues.id"), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # arXiv 首次发布时间
    arxiv_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # arXiv 版本更新时间
    journal_ref: Mapped[str | None] = mapped_column(Text, nullable=True)  # arXiv 正式出处线索（如 "Accepted at ICSE 2026"）
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)  # arXiv comments 字段

    is_ai4se_candidate: Mapped[bool] = mapped_column(Boolean, default=False)  # 关键词初筛命中
    is_ai4se_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)  # LLM 精标确认
    match_status: Mapped[str] = mapped_column(String(16), default=MatchStatus.NONE.value)
    match_candidates: Mapped[list[dict] | None] = mapped_column(  # 歧义时多候选快照，人工复核用
        JSON, nullable=True, default=None
    )
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)  # M8 OpenAlex 被引数
    summary_zh: Mapped[str | None] = mapped_column(Text, nullable=True)  # LLM 中文摘要
    highlights: Mapped[dict | None] = mapped_column(  # LLM 亮点速读 {contribution, limitation}
        JSON, nullable=True, default=None
    )
    deep_summary: Mapped[dict | None] = mapped_column(  # M7 AI 深度摘要（按需生成后缓存）
        JSON, nullable=True, default=None
    )
    status: Mapped[str] = mapped_column(String(16), default=PaperStatus.FETCHED.value)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    venue: Mapped["Venue | None"] = relationship(back_populates="papers")  # noqa: F821
    author_links: Mapped[list["PaperAuthor"]] = relationship(  # noqa: F821
        back_populates="paper", order_by="PaperAuthor.position", cascade="all, delete-orphan"
    )
    topic_links: Mapped[list["PaperTopic"]] = relationship(  # noqa: F821
        back_populates="paper", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Paper {self.arxiv_id or self.title[:50]}>"


class PaperAuthor(Base):
    """论文-作者 N:M 关联（含作者顺序）。"""

    __tablename__ = "paper_authors"
    __table_args__ = (UniqueConstraint("paper_id", "position", name="uq_paper_author_position"),)

    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    affiliation: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 机构（arXiv 每作者机构，规则归一化）

    paper: Mapped[Paper] = relationship(back_populates="author_links")
    author: Mapped["Author"] = relationship(back_populates="paper_links")  # noqa: F821
