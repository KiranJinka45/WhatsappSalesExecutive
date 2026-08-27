import uuid
from sqlalchemy import Column, String, Text, Numeric, Integer, ForeignKey, DateTime, Index, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from .database import Base

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    logo_url = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    whatsapp_number = Column(String(20), unique=True, nullable=True)
    whatsapp_business_account_id = Column(String(100), nullable=True)
    whatsapp_phone_number_id = Column(String(100), nullable=True)
    whatsapp_access_token = Column(Text, nullable=True)
    is_whatsapp_connected = Column(Integer, default=0)
    whatsapp_onboarding_state = Column(String(50), default="NOT_CONNECTED")
    whatsapp_onboarding_metadata = Column(JSONB, default=dict)
    policies = Column(JSONB, default=dict)  # shipping, return, exchange, general FAQs
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="organization", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="organization", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="organization")
    customer_memories = relationship("CustomerMemory", back_populates="organization", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="organization", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # 'owner', 'staff'
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="users")
    conversations = relationship("Conversation", back_populates="assigned_user")


class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)

    organization = relationship("Organization", back_populates="categories")
    products = relationship("Product", back_populates="category")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("idx_products_org_category_price", "organization_id", "category_id", "price"),
        UniqueConstraint("organization_id", "sku", name="uq_products_org_sku"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    sku = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    gender = Column(String(50), nullable=True)  # 'Men', 'Women', 'Unisex'
    price = Column(Numeric(10, 2), nullable=False)
    color = Column(String(100), nullable=True)
    fabric = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    sizes = Column(ARRAY(String(50)), default=list)  # ['S', 'M', 'L', 'XL']
    stock_count = Column(Integer, default=0)
    image_urls = Column(ARRAY(Text), default=list)
    video_urls = Column(ARRAY(Text), default=list)
    embedding = Column(Vector(768), nullable=True)  # pgvector embedding (Gemini text-embedding-004)
    embedding_status = Column(String(50), default="pending", server_default="pending")  # 'pending', 'processing', 'completed', 'failed'
    image_embedding = Column(Vector(3072), nullable=True)  # pgvector embedding (Gemini multimodal embedding-2)
    image_embedding_status = Column(String(50), default="pending", server_default="pending")  # 'pending', 'processing', 'completed', 'failed'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="products")
    category = relationship("Category", back_populates="products")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("idx_conversations_org_status", "organization_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False)
    customer_phone = Column(String(20), nullable=False, index=True)
    customer_name = Column(String(255), nullable=True)
    status = Column(String(50), default="AI_ACTIVE", index=True)  # 'AI_ACTIVE', 'WAITING_APPROVAL', 'HUMAN_TAKEOVER', 'CLOSED'
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)  # states budget, size/color pref, etc.
    lead_score = Column(Integer, default=0)
    escalation_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", back_populates="conversations")
    assigned_user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at.asc()")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("idx_messages_conv_created_at", "conversation_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender = Column(String(50), nullable=False)  # 'customer', 'ai', 'human'
    message_type = Column(String(50), default="text")  # 'text', 'image', 'video', 'interactive'
    content = Column(Text, nullable=False)
    media_url = Column(Text, nullable=True)
    status = Column(String(50), default="sent", server_default="sent")  # 'pending', 'sent', 'failed'
    error_message = Column(Text, nullable=True)
    detected_language = Column(String(50), nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)  # Explainability: retrieved_products, rejected_products, policy_checks, confidence
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")


class CustomerMemory(Base):
    __tablename__ = "customer_memories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    customer_phone = Column(String(20), nullable=False, index=True)
    preferred_sizes = Column(ARRAY(String(50)), default=list)
    preferred_colors = Column(ARRAY(String(100)), default=list)
    preferred_fabrics = Column(ARRAY(String(255)), default=list)
    budget_min = Column(Numeric(10, 2), nullable=True)
    budget_max = Column(Numeric(10, 2), nullable=True)
    style_notes = Column(Text, nullable=True)  # Free-form AI-generated style profile
    total_purchases = Column(Integer, default=0)
    total_spent = Column(Numeric(12, 2), default=0)
    last_interaction = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="customer_memories")


class Order(Base):
    __tablename__ = "orders"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True)
    customer_phone = Column(String(20), nullable=False, index=True)
    status = Column(String(50), default="pending")  # 'pending', 'payment_sent', 'paid', 'shipped', 'delivered', 'cancelled'
    payment_method = Column(String(50), nullable=True)  # 'cod', 'upi', 'razorpay', 'stripe'
    payment_id = Column(String(255), nullable=True)  # External payment reference
    total_amount = Column(Numeric(12, 2), nullable=False)
    shipping_address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", back_populates="orders")
    conversation = relationship("Conversation")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name = Column(String(255), nullable=False)  # Denormalized for order history
    product_sku = Column(String(100), nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Numeric(10, 2), nullable=False)
    selected_size = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")


class RecommendationFeedback(Base):
    __tablename__ = "recommendation_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    product_sku = Column(String(100), nullable=False)
    rating = Column(Integer, nullable=False)  # 1 for thumbs up, -1 for thumbs down
    reason = Column(String(255), nullable=True)  # 'Wrong Product', 'Wrong Color', 'Wrong Budget', etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    message = relationship("Message")


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    
    status = Column(String(50), default="WAITING_APPROVAL")  # 'DRAFT_READY', 'WAITING_APPROVAL', 'APPROVED', 'DISPATCHING', 'SENT', 'SEND_FAILED', 'REJECTED', 'EXPIRED', 'CANCELLED'
    reason = Column(String(255), nullable=False)      # e.g., 'Requested 15% discount'
    proposed_response = Column(Text, nullable=False)  # Proposed AI reply text
    ai_recommendation = Column(String(50), nullable=True)  # 'approve', 'reject'
    risk_score = Column(Integer, default=0)           # 0 - 100 risk score
    
    # Pilot Human-Approval & exact-message integrity fields
    approved_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    edited_by_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    edited_response = Column(Text, nullable=True)
    message_hash = Column(String(64), nullable=True)  # SHA-256 hash of approved/edited response
    version = Column(Integer, default=1)
    price_snapshot = Column(JSONB, default=dict)       # SKU -> price mapping at draft generation
    stock_snapshot = Column(JSONB, default=dict)       # SKU -> stock count at draft generation
    expires_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    # Audit trail metadata
    llm_model = Column(String(100), nullable=True)
    prompt_version = Column(String(50), default="v1")
    retrieval_ids = Column(JSONB, default=list)       # JSON list of SKUs retrieved
    grounding_score = Column(Numeric(5, 2), default=0.0)
    decision_engine_version = Column(String(50), default="v1.0")
    rule_triggered = Column(String(100), nullable=True)
    
    metadata_ = Column("metadata", JSONB, default=dict) # any other extra details
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    conversation = relationship("Conversation")
    organization = relationship("Organization")
    approved_by_user = relationship("User", foreign_keys=[approved_by_user_id])
    edited_by_user = relationship("User", foreign_keys=[edited_by_user_id])
    notifications = relationship("Notification", back_populates="approval_request", cascade="all, delete-orphan")
    audit_logs = relationship("ApprovalAuditLog", back_populates="approval_request", cascade="all, delete-orphan")


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    approval_request_id = Column(UUID(as_uuid=True), ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=True)
    
    type = Column(String(100), nullable=False) # e.g., 'ApprovalCreated', 'ApprovalApproved', 'ApprovalRejected', 'ApprovalEdited'
    status = Column(String(50), default="unread") # 'unread', 'read'
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    read_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization")
    approval_request = relationship("ApprovalRequest", back_populates="notifications")


class ApprovalAuditLog(Base):
    __tablename__ = "approval_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    approval_request_id = Column(UUID(as_uuid=True), ForeignKey("approval_requests.id", ondelete="CASCADE"), nullable=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    action = Column(String(50), nullable=False)  # 'VIEWED', 'APPROVED', 'DRAFT_EDITED', 'REJECTED', 'TAKEN_OVER', 'SENT', 'SEND_FAILED', 'EXPIRED', 'KILL_SWITCH_ACTIVATED', 'KILL_SWITCH_DEACTIVATED', 'AMBIGUOUS_PROVIDER_TIMEOUT', 'CANCELLED'
    previous_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False)
    message_content = Column(Text, nullable=True)
    message_hash = Column(String(64), nullable=True)
    revalidation_passed = Column(Boolean, default=True)
    metadata_ = Column("metadata", JSONB, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization")
    approval_request = relationship("ApprovalRequest", back_populates="audit_logs")
    user = relationship("User")


class WhatsappOnboardingAuditLog(Base):
    __tablename__ = "whatsapp_onboarding_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    action = Column(String(50), nullable=False)  # 'REQUEST_CODE', 'VERIFY_CODE', 'ACTIVATE_NUMBER', 'STATE_TRANSITION', 'ERROR'
    previous_state = Column(String(50), nullable=True)
    new_state = Column(String(50), nullable=False)
    error_category = Column(String(100), nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)
    correlation_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization")
    user = relationship("User")


class OutboundMessage(Base):
    __tablename__ = "outbound_messages"
    __table_args__ = (
        Index("idx_outbound_org_status", "organization_id", "status"),
        UniqueConstraint("approval_request_id", "message_version", name="uq_outbound_approval_version"),
        UniqueConstraint("provider_idempotency_key", name="uq_outbound_provider_idempotency"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    approval_request_id = Column(UUID(as_uuid=True), ForeignKey("approval_requests.id", ondelete="SET NULL"), nullable=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    message_version = Column(Integer, default=1, server_default="1", nullable=False)
    provider_idempotency_key = Column(String(100), unique=True, nullable=False, index=True)
    payload_hash = Column(String(64), nullable=False)
    recipient_phone = Column(String(30), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(30), default="PENDING", server_default="PENDING", nullable=False, index=True)  # 'PENDING', 'DISPATCHING', 'SENT', 'FAILED', 'UNKNOWN_PROVIDER_OUTCOME', 'CANCELLED'
    provider_message_id = Column(String(100), nullable=True, index=True)
    attempt_count = Column(Integer, default=0, server_default="0", nullable=False)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization")
    conversation = relationship("Conversation")
    approval_request = relationship("ApprovalRequest")


from sqlalchemy import event, DDL

# Register database Row-Level Security (RLS) policies dynamically on create
# These policies are FAIL-CLOSED: if app.current_tenant is not set or is empty,
# NO rows are visible. Only an explicitly-set tenant UUID grants access.
def register_rls_policies():
    tenant_id_expr = "current_setting('app.current_tenant', true)"
    # Fail-closed: empty/null tenant → no access; set tenant → only matching rows
    fail_closed_using = (
        f"organization_id = nullif({tenant_id_expr}, '')::uuid"
    )
    fail_closed_org_using = (
        f"id = nullif({tenant_id_expr}, '')::uuid"
    )
    
    org_ddl = DDL(
        f"ALTER TABLE organizations ENABLE ROW LEVEL SECURITY; "
        f"ALTER TABLE organizations FORCE ROW LEVEL SECURITY; "
        f"DROP POLICY IF EXISTS organizations_tenant_policy ON organizations; "
        f"CREATE POLICY organizations_tenant_policy ON organizations "
        f"USING ({fail_closed_org_using}) "
        f"WITH CHECK ({fail_closed_org_using});"
    )
    event.listen(Organization.__table__, "after_create", org_ddl)
    
    tenant_tables = [
        (User, "users"),
        (Category, "categories"),
        (Product, "products"),
        (Conversation, "conversations"),
        (CustomerMemory, "customer_memories"),
        (Order, "orders"),
        (ApprovalRequest, "approval_requests"),
        (Notification, "notifications"),
        (OutboundMessage, "outbound_messages")
    ]
    for model_cls, table_name in tenant_tables:
        ddl = DDL(
            f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY; "
            f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY; "
            f"DROP POLICY IF EXISTS {table_name}_tenant_policy ON {table_name}; "
            f"CREATE POLICY {table_name}_tenant_policy ON {table_name} "
            f"USING ({fail_closed_using}) "
            f"WITH CHECK ({fail_closed_using});"
        )
        event.listen(model_cls.__table__, "after_create", ddl)

    # Separate setup for approval_audit_logs to prevent creating broad ALL, UPDATE, or DELETE policies
    audit_ddl = DDL(
        f"ALTER TABLE approval_audit_logs ENABLE ROW LEVEL SECURITY; "
        f"ALTER TABLE approval_audit_logs FORCE ROW LEVEL SECURITY; "
        f"DROP POLICY IF EXISTS approval_audit_logs_tenant_policy ON approval_audit_logs; "
        f"DROP POLICY IF EXISTS approval_audit_logs_tenant_select_policy ON approval_audit_logs; "
        f"DROP POLICY IF EXISTS approval_audit_logs_tenant_insert_policy ON approval_audit_logs; "
        f"CREATE POLICY approval_audit_logs_tenant_select_policy ON approval_audit_logs "
        f"FOR SELECT USING ({fail_closed_using}); "
        f"CREATE POLICY approval_audit_logs_tenant_insert_policy ON approval_audit_logs "
        f"FOR INSERT WITH CHECK ({fail_closed_using});"
    )
    event.listen(ApprovalAuditLog.__table__, "after_create", audit_ddl)

    onboarding_audit_ddl = DDL(
        f"ALTER TABLE whatsapp_onboarding_audit_logs ENABLE ROW LEVEL SECURITY; "
        f"ALTER TABLE whatsapp_onboarding_audit_logs FORCE ROW LEVEL SECURITY; "
        f"DROP POLICY IF EXISTS onboarding_audit_logs_tenant_select_policy ON whatsapp_onboarding_audit_logs; "
        f"DROP POLICY IF EXISTS onboarding_audit_logs_tenant_insert_policy ON whatsapp_onboarding_audit_logs; "
        f"CREATE POLICY onboarding_audit_logs_tenant_select_policy ON whatsapp_onboarding_audit_logs "
        f"FOR SELECT USING ({fail_closed_using}); "
        f"CREATE POLICY onboarding_audit_logs_tenant_insert_policy ON whatsapp_onboarding_audit_logs "
        f"FOR INSERT WITH CHECK ({fail_closed_using});"
    )
    event.listen(WhatsappOnboardingAuditLog.__table__, "after_create", onboarding_audit_ddl)
        
    msg_subquery = f"conversation_id IN (SELECT id FROM conversations WHERE {fail_closed_using})"
    msg_ddl = DDL(
        f"ALTER TABLE messages ENABLE ROW LEVEL SECURITY; "
        f"ALTER TABLE messages FORCE ROW LEVEL SECURITY; "
        f"DROP POLICY IF EXISTS messages_tenant_policy ON messages; "
        f"CREATE POLICY messages_tenant_policy ON messages "
        f"USING ({msg_subquery}) "
        f"WITH CHECK ({msg_subquery});"
    )
    event.listen(Message.__table__, "after_create", msg_ddl)
    
    item_subquery = f"order_id IN (SELECT id FROM orders WHERE {fail_closed_using})"
    item_ddl = DDL(
        f"ALTER TABLE order_items ENABLE ROW LEVEL SECURITY; "
        f"ALTER TABLE order_items FORCE ROW LEVEL SECURITY; "
        f"DROP POLICY IF EXISTS order_items_tenant_policy ON order_items; "
        f"CREATE POLICY order_items_tenant_policy ON order_items "
        f"USING ({item_subquery}) "
        f"WITH CHECK ({item_subquery});"
    )
    event.listen(OrderItem.__table__, "after_create", item_ddl)
    
    feedback_subquery = (
        f"message_id IN ("
        f"    SELECT m.id FROM messages m "
        f"    JOIN conversations c ON m.conversation_id = c.id "
        f"    WHERE {fail_closed_using}"
        f")"
    )
    feedback_ddl = DDL(
        f"ALTER TABLE recommendation_feedback ENABLE ROW LEVEL SECURITY; "
        f"ALTER TABLE recommendation_feedback FORCE ROW LEVEL SECURITY; "
        f"DROP POLICY IF EXISTS recommendation_feedback_tenant_policy ON recommendation_feedback; "
        f"CREATE POLICY recommendation_feedback_tenant_policy ON recommendation_feedback "
        f"USING ({feedback_subquery}) "
        f"WITH CHECK ({feedback_subquery});"
    )
    event.listen(RecommendationFeedback.__table__, "after_create", feedback_ddl)

register_rls_policies()

