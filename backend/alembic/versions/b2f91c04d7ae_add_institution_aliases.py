"""add institution_aliases table

Revision ID: b2f91c04d7ae
Revises: eaf135077f81
Create Date: 2026-08-20 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2f91c04d7ae'
down_revision: Union[str, Sequence[str], None] = 'eaf135077f81'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "institution_aliases",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("alias", sa.String(length=255), nullable=False),
        sa.Column("canonical", sa.String(length=255), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_institution_aliases_alias", "institution_aliases", ["alias"], unique=True)
    op.create_index("ix_institution_aliases_canonical", "institution_aliases", ["canonical"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_institution_aliases_canonical", table_name="institution_aliases")
    op.drop_index("ix_institution_aliases_alias", table_name="institution_aliases")
    op.drop_table("institution_aliases")
