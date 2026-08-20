"""机构别名表（机构功能：alias→canonical 数据驱动合并库）。

机构名经 normalize_institution 归一化后仍存在变体（邮政/城市后缀、实验室排列、
连字符等）。本表把 alias 精确映射到 canonical，写库时落 canonical（见
institution_service.load_institution_alias_map / normalize.apply_institution_alias）。
数据驱动：课题组可直接增删别名，无需改代码。
"""
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class InstitutionAlias(Base):
    __tablename__ = "institution_aliases"

    id: Mapped[int] = mapped_column(primary_key=True)
    alias: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # 归一化后的完整机构串
    canonical: Mapped[str] = mapped_column(String(255), index=True)  # 合并后的权威机构名
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
