"""论文相关 Pydantic 响应模型（与 ORM 分离，见 CLAUDE.md 第 7 章）。"""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class VenueBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    short_name: str
    full_name: str
    type: str | None = None  # conference/journal（导出 BibTeX 条目类型用）


class TopicBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name_zh: str


class PaperMarks(BaseModel):
    """个性化阅读标记集合（M6）：bookmark 收藏 / read 已读 / read_later 稍后读。"""

    bookmark: bool = False
    read: bool = False
    read_later: bool = False


class Highlights(BaseModel):
    """LLM 亮点速读（M6）：一句话核心贡献 + 一句话局限。"""

    contribution: str | None = None
    limitation: str | None = None


class PaperListItem(BaseModel):
    """列表项：双链接（arxiv_url + dblp_url/doi）+ 主题标签 + 会议信息。"""

    id: int
    title: str
    authors: list[str]
    venue: VenueBrief | None
    topics: list[TopicBrief]
    year: int | None
    published_at: date | None
    is_ai4se_confirmed: bool
    citation_count: int | None = None  # M8 OpenAlex 调整后：Crossref/S2 双源引用数
    arxiv_url: str | None
    pdf_url: str | None = None  # M7 arXiv PDF 直链
    dblp_url: str | None
    doi: str | None
    marks: PaperMarks = PaperMarks()


class AuthorBrief(BaseModel):
    """详情页作者（M12 机构功能）：姓名 + 机构（可点击跳机构详情页）。"""

    name: str
    affiliation: str | None = None


class PaperDetail(PaperListItem):
    """详情：列表字段 + 摘要/中文摘要/亮点速读/匹配状态 + 相关论文推荐。

    authors 覆盖为带机构的 AuthorBrief[]（列表页仍为 string[]，见 PaperListItem）。
    """

    authors: list[AuthorBrief]  # noqa: F811（覆盖父类字段类型）
    abstract: str | None
    summary_zh: str | None
    highlights: Highlights | None = None
    is_ai4se_candidate: bool
    match_status: str
    status: str
    related: list[PaperListItem] = []


class PaperPage(BaseModel):
    """统一分页响应（CLAUDE.md 第 7 章约定）。"""

    items: list[PaperListItem]
    total: int
    page: int
    page_size: int


class MarkRequest(BaseModel):
    """设置/取消个性化标记：type + value（幂等）。"""

    type: Literal["bookmark", "read", "read_later"]
    value: bool = True
