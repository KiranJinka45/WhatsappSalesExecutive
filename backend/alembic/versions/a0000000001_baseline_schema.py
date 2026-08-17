"""baseline_schema

Revision ID: a0000000001
Revises: 
Create Date: 2026-08-14 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a0000000001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 1. organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('logo_url', sa.Text(), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('whatsapp_number', sa.String(length=20), nullable=True),
        sa.Column('whatsapp_business_account_id', sa.String(length=100), nullable=True),
        sa.Column('whatsapp_phone_number_id', sa.String(length=100), nullable=True),
        sa.Column('whatsapp_access_token', sa.Text(), nullable=True),
        sa.Column('is_whatsapp_connected', sa.Integer(), server_default='0', nullable=True),
        sa.Column('policies', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('whatsapp_number')
    )

    # 2. users
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )

    # 3. categories
    op.create_table(
        'categories',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 4. products
    op.create_table(
        'products',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('category_id', sa.UUID(), nullable=True),
        sa.Column('sku', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('gender', sa.String(length=50), nullable=True),
        sa.Column('price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('color', sa.String(length=100), nullable=True),
        sa.Column('fabric', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sizes', postgresql.ARRAY(sa.String(length=50)), nullable=True),
        sa.Column('stock_count', sa.Integer(), server_default='0', nullable=True),
        sa.Column('image_urls', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('video_urls', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('embedding_status', sa.String(length=50), server_default='pending', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_products_sku'), 'products', ['sku'], unique=False)
    op.create_index('idx_products_org_category_price', 'products', ['organization_id', 'category_id', 'price'], unique=False)

    op.execute('ALTER TABLE products ADD COLUMN embedding vector(768);')

    # 5. conversations
    op.create_table(
        'conversations',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('customer_phone', sa.String(length=20), nullable=False),
        sa.Column('customer_name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='AI_ACTIVE', nullable=True),
        sa.Column('assigned_user_id', sa.UUID(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('lead_score', sa.Integer(), server_default='0', nullable=True),
        sa.Column('escalation_reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['assigned_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_conversations_customer_phone'), 'conversations', ['customer_phone'], unique=False)
    op.create_index(op.f('ix_conversations_status'), 'conversations', ['status'], unique=False)
    op.create_index('idx_conversations_org_status', 'conversations', ['organization_id', 'status'], unique=False)

    # 6. messages
    op.create_table(
        'messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('sender', sa.String(length=50), nullable=False),
        sa.Column('message_type', sa.String(length=50), server_default='text', nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('media_url', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), server_default='sent', nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('detected_language', sa.String(length=50), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_messages_conv_created_at', 'messages', ['conversation_id', 'created_at'], unique=False)

    # 7. customer_memories
    op.create_table(
        'customer_memories',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('customer_phone', sa.String(length=20), nullable=False),
        sa.Column('preferred_sizes', postgresql.ARRAY(sa.String(length=50)), nullable=True),
        sa.Column('preferred_colors', postgresql.ARRAY(sa.String(length=100)), nullable=True),
        sa.Column('preferred_fabrics', postgresql.ARRAY(sa.String(length=255)), nullable=True),
        sa.Column('budget_min', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('budget_max', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('style_notes', sa.Text(), nullable=True),
        sa.Column('total_purchases', sa.Integer(), server_default='0', nullable=True),
        sa.Column('total_spent', sa.Numeric(precision=12, scale=2), server_default='0', nullable=True),
        sa.Column('last_interaction', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customer_memories_customer_phone'), 'customer_memories', ['customer_phone'], unique=False)

    # 8. orders
    op.create_table(
        'orders',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=True),
        sa.Column('customer_phone', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='pending', nullable=True),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('payment_id', sa.String(length=255), nullable=True),
        sa.Column('total_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('shipping_address', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_orders_customer_phone'), 'orders', ['customer_phone'], unique=False)

    # 9. order_items
    op.create_table(
        'order_items',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('order_id', sa.UUID(), nullable=False),
        sa.Column('product_id', sa.UUID(), nullable=True),
        sa.Column('product_name', sa.String(length=255), nullable=False),
        sa.Column('product_sku', sa.String(length=100), nullable=False),
        sa.Column('quantity', sa.Integer(), server_default='1', nullable=True),
        sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('selected_size', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # 10. recommendation_feedback
    op.create_table(
        'recommendation_feedback',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('message_id', sa.UUID(), nullable=False),
        sa.Column('product_sku', sa.String(length=100), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['message_id'], ['messages.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 11. approval_requests
    op.create_table(
        'approval_requests',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('conversation_id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=50), server_default='WAITING_APPROVAL', nullable=True),
        sa.Column('reason', sa.String(length=255), nullable=False),
        sa.Column('proposed_response', sa.Text(), nullable=False),
        sa.Column('ai_recommendation', sa.String(length=50), nullable=True),
        sa.Column('risk_level', sa.String(length=50), nullable=True),
        sa.Column('approved_by_user_id', sa.UUID(), nullable=True),
        sa.Column('edited_by_user_id', sa.UUID(), nullable=True),
        sa.Column('edited_response', sa.Text(), nullable=True),
        sa.Column('message_hash', sa.String(length=64), nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=True),
        sa.Column('price_snapshot', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('stock_snapshot', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['edited_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 12. approval_audit_logs
    op.create_table(
        'approval_audit_logs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('organization_id', sa.UUID(), nullable=False),
        sa.Column('approval_request_id', sa.UUID(), nullable=True),
        sa.Column('conversation_id', sa.UUID(), nullable=True),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('previous_status', sa.String(length=50), nullable=True),
        sa.Column('new_status', sa.String(length=50), nullable=False),
        sa.Column('message_content', sa.Text(), nullable=True),
        sa.Column('message_hash', sa.String(length=64), nullable=True),
        sa.Column('revalidation_passed', sa.Boolean(), server_default=sa.text('true'), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['approval_request_id'], ['approval_requests.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('approval_audit_logs')
    op.drop_table('approval_requests')
    op.drop_table('recommendation_feedback')
    op.drop_table('order_items')
    op.drop_index(op.f('ix_orders_customer_phone'), table_name='orders')
    op.drop_table('orders')
    op.drop_index(op.f('ix_customer_memories_customer_phone'), table_name='customer_memories')
    op.drop_table('customer_memories')
    op.drop_index('idx_messages_conv_created_at', table_name='messages')
    op.drop_table('messages')
    op.drop_index('idx_conversations_org_status', table_name='conversations')
    op.drop_index(op.f('ix_conversations_status'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_customer_phone'), table_name='conversations')
    op.drop_table('conversations')
    op.drop_index('idx_products_org_category_price', table_name='products')
    op.drop_index(op.f('ix_products_sku'), table_name='products')
    op.drop_table('products')
    op.drop_table('categories')
    op.drop_table('users')
    op.drop_table('organizations')
