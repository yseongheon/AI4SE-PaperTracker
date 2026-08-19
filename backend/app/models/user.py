"""用户（users 表，M9）：课题组账号体系，pbkdf2 密码哈希。

无邮箱验证（内网工具），username 唯一即可登录。
"""
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256))  # pbkdf2$iter$salt$hash
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    marks: Mapped[list["UserMark"]] = relationship(back_populates="user")  # noqa: F821

    def __repr__(self) -> str:
        return f"<User {self.username}>"
