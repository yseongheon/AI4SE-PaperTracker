"""A 会接口（M3）：列表 + 计数。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.venue import VenueWithCount
from app.services import stats_service

router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("", response_model=list[VenueWithCount])
def list_venues(db: Session = Depends(get_db)) -> list[dict]:
    return stats_service.venue_counts(db)
