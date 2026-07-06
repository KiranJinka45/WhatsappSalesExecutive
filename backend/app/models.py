import uuid
from sqlalchemy import Column, String, Text, Numeric, Integer, ForeignKey, DateTime
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
    policies = Column(JSONB, default=dict)  # shipping, return, exchange, general FAQs
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="organization", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="organization", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="organization", cascade="all, delete-orphan")


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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    sku = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    gender = Column(String(50), nullable=True)  # 'Men', 'Women', 'Unisex'
    price = Column(Numeric(10, 2), nullable=False)
    color = Column(String(100), nullable=False)
    fabric = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    sizes = Column(ARRAY(String(50)), default=list)  # ['S', 'M', 'L', 'XL']
    stock_count = Column(Integer, default=0)
    image_urls = Column(ARRAY(Text), default=list)
    video_urls = Column(ARRAY(Text), default=list)
    embedding = Column(Vector(768), nullable=True)  # pgvector embedding (Gemini text-embedding-004)
    embedding_status = Column(String(50), default="pending", server_default="pending")  # 'pending', 'processing', 'completed', 'failed'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="products")
    category = relationship("Category", back_populates="products")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    customer_name = Column(String(255), nullable=True)
    status = Column(String(50), default="ai_active")  # 'ai_active', 'human_takeover', 'resolved'
    assigned_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    metadata_ = Column("metadata", JSONB, default=dict)  # states budget, size/color pref, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization = relationship("Organization", back_populates="conversations")
    assigned_user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender = Column(String(50), nullable=False)  # 'customer', 'ai', 'human'
    message_type = Column(String(50), default="text")  # 'text', 'image', 'video', 'interactive'
    content = Column(Text, nullable=False)
    media_url = Column(Text, nullable=True)
    status = Column(String(50), default="sent", server_default="sent")  # 'pending', 'sent', 'failed'
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")
