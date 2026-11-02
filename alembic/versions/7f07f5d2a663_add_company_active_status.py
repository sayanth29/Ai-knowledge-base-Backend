"""add company active status

Revision ID: 7f07f5d2a663
Revises: a1f2dfd951bb
Create Date: 2026-10-09 19:16:29.283822

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f07f5d2a663'
down_revision: Union[str, Sequence[str], None] = 'a1f2dfd951bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'companies',
        'is_active',
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text('true'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'companies',
        'is_active',
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=None,
    )
