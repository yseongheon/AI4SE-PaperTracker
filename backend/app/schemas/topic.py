"""主题响应模型（含计数，供前端筛选侧栏）。"""
from pydantic import BaseModel


class TopicWithCount(BaseModel):
    id: int
    slug: str
    name_zh: str
    description: str | None
    paper_count: int
