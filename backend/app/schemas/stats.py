"""统计响应模型（DR-020 趋势图数据）。"""

from pydantic import BaseModel


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
