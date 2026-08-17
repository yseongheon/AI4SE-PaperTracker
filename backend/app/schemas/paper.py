"""论文相关 Pydantic 响应模型（与 ORM 分离，见 CLAUDE.md 第 7 章）。"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class VenueBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    short_name: str
    full_name: str


class TopicBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name_zh: str


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
    arxiv_url: str | None
    dblp_url: str | None
    doi: str | None


class PaperDetail(PaperListItem):
    """详情：列表字段 + 摘要/中文摘要/匹配状态。"""

    abstract: str | None
    summary_zh: str | None
    is_ai4se_candidate: bool
    match_status: str
    status: str


class PaperPage(BaseModel):
    """统一分页响应（CLAUDE.md 第 7 章约定）。"""

    items: list[PaperListItem]
    total: int
    page: int
    page_size: int
