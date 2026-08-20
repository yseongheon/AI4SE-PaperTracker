"""add affiliation to paper_authors

Revision ID: eaf135077f81
Revises: 8e07230e0ec0
Create Date: 2026-08-20 15:18:48.076794

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eaf135077f81'
down_revision: Union[str, Sequence[str], None] = '8e07230e0ec0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "paper_authors",
        sa.Column("affiliation", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("paper_authors", "affiliation")
