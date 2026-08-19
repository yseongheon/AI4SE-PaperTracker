"""M9: add users table and user_id to user_marks

SQLite 不支持直接改主键/非空约束 → 用 batch_alter_table 重建表；
旧标记数据迁移归首个注册用户（user_id=1，M9 拍板）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e07230e0ec0'
down_revision: Union[str, Sequence[str], None] = 'f05569ab478b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('email', sa.String(length=128), nullable=True),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)

    # user_marks 显式重建（SQLite 无约束名反射，batch 的 drop_constraint 不可靠）：
    # 加 user_id 列 + 复合主键 (user_id, paper_id, mark_type) + FK，旧数据归 user 1（M9 拍板）
    op.execute("ALTER TABLE user_marks RENAME TO user_marks_old")
    op.create_table(
        'user_marks',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('paper_id', sa.Integer(), nullable=False),
        sa.Column('mark_type', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['paper_id'], ['papers.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_user_marks_user_id'),
        sa.PrimaryKeyConstraint('user_id', 'paper_id', 'mark_type'),
    )
    op.execute(
        "INSERT INTO user_marks (user_id, paper_id, mark_type, created_at) "
        "SELECT 1, paper_id, mark_type, created_at FROM user_marks_old"
    )
    op.drop_table('user_marks_old')


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE user_marks RENAME TO user_marks_old")
    op.create_table(
        'user_marks',
        sa.Column('paper_id', sa.Integer(), nullable=False),
        sa.Column('mark_type', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['paper_id'], ['papers.id']),
        sa.PrimaryKeyConstraint('paper_id', 'mark_type'),
    )
    op.execute(
        "INSERT INTO user_marks (paper_id, mark_type, created_at) "
        "SELECT paper_id, mark_type, created_at FROM user_marks_old"
    )
    op.drop_table('user_marks_old')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
