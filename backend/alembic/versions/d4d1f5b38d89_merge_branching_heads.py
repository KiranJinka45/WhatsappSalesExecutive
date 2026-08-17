"""merge branching heads

Revision ID: d4d1f5b38d89
Revises: c3a4b1d2e5f6, e7f8a9b0c1d2
Create Date: 2026-08-14 19:07:52.750763

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4d1f5b38d89'
down_revision: Union[str, None] = ('c3a4b1d2e5f6', 'e7f8a9b0c1d2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
