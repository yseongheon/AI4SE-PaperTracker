"""统计响应模型（DR-020 趋势图数据；M12 机构详情）。"""

from pydantic import BaseModel


class InstitutionTopicStat(BaseModel):
    """机构主题分布（M12）：slug/name_zh/count（DISTINCT 论文计数）。"""

    slug: str
    name_zh: str
    count: int


class CoInstitution(BaseModel):
    """合作机构（M12）：机构名 + 共同论文数（DISTINCT）。"""

    name: str
    count: int


class InstitutionDetailResponse(BaseModel):
    """机构详情（M12）：统计 + 主题分布 + 合作机构。"""

    name: str
    paper_count: int
    ai4se_count: int
    topics: list[InstitutionTopicStat]
    co_institutions: list[CoInstitution]


class TrendSeries(BaseModel):
    """一条折线/柱：key 为 slug/short_name，name 为展示名。"""

    key: str
    name: str
    values: list[int]


class TrendResponse(BaseModel):
    """趋势时间序列：labels 为横轴（按天返回原始计数，聚合粒度由前端决定）。

    group_by=topic|venue 时 labels 为连续日期；group_by=year 时 labels 为年份。
    """

    group_by: str
    start: str | None
    end: str | None
    labels: list[str]
    series: list[TrendSeries]


class TopicCount(BaseModel):
    """作者/机构榜主要主题条目：slug/name_zh/count。"""

    slug: str
    name_zh: str
    count: int


class AuthorStat(BaseModel):
    """作者榜条目：论文数（DISTINCT）+ AI4SE 数 + 主要主题 + 机构。"""

    id: int
    name: str
    paper_count: int
    ai4se_count: int
    top_topics: list[TopicCount]
    affiliation: str | None = None


class InstitutionStat(BaseModel):
    """机构榜条目：论文数（DISTINCT）+ AI4SE 数 + 主要主题。"""

    name: str
    paper_count: int
    ai4se_count: int
    top_topics: list[TopicCount]


class AuthorPage(BaseModel):
    """作者榜分页响应（M13 全量+分页，遵循 {items,total,page,page_size} 约定）。"""

    items: list[AuthorStat]
    total: int
    page: int
    page_size: int


class InstitutionPage(BaseModel):
    """机构榜分页响应（M13 全量+分页）。"""

    items: list[InstitutionStat]
    total: int
    page: int
    page_size: int
