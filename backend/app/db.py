"""数据库引擎与会话（M1 建表，M0 仅占位）。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """FastAPI 依赖：每个请求一个会话，请求结束关闭。"""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
