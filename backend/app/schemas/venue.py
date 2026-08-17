"""会议/期刊响应模型（含计数）。"""
from pydantic import BaseModel


class VenueWithCount(BaseModel):
    id: int
    short_name: str
    full_name: str
    rank: str
    paper_count: int
