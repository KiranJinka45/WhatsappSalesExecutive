"""Add uq_products_org_sku constraint and make color and fabric nullable

Revision ID: c3a4b1d2e5f6
Revises: bcf53b84a362
Create Date: 2026-08-13 13:42:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3a4b1d2e5f6'
down_revision: Union[str, None] = 'bcf53b84a362'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('products', 'color', existing_type=sa.String(length=100), nullable=True)
    op.alter_column('products', 'fabric', existing_type=sa.String(length=255), nullable=True)
    op.create_unique_constraint('uq_products_org_sku', 'products', ['organization_id', 'sku'])


def downgrade() -> None:
    op.drop_constraint('uq_products_org_sku', 'products', type_='unique')
    op.alter_column('products', 'fabric', existing_type=sa.String(length=255), nullable=False)
    op.alter_column('products', 'color', existing_type=sa.String(length=100), nullable=False)
