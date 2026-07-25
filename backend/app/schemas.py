from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from uuid import UUID

# Token
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[str] = None

class LoginResponse(BaseModel):
    status: str = "success"
    message: str = "Successfully authenticated"
    access_token: Optional[str] = None


# Organization
class OrganizationBase(BaseModel):
    name: str
    logo_url: Optional[str] = None
    address: Optional[str] = None
    whatsapp_number: Optional[str] = None
    policies: Dict[str, Any] = Field(default_factory=dict)

class OrganizationCreate(OrganizationBase):
    pass

class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    address: Optional[str] = None
    whatsapp_number: Optional[str] = None
    policies: Optional[Dict[str, Any]] = None

class OrganizationOut(OrganizationBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# User
class UserBase(BaseModel):
    email: EmailStr
    name: str

class UserCreate(UserBase):
    password: str
    organization_name: Optional[str] = None  # Needed if creating organization during signup

class UserOut(UserBase):
    id: UUID
    organization_id: UUID
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Category
class CategoryBase(BaseModel):
    name: str

class CategoryCreate(CategoryBase):
    pass

class CategoryOut(CategoryBase):
    id: UUID
    organization_id: UUID

    model_config = ConfigDict(from_attributes=True)


# Product
class ProductBase(BaseModel):
    sku: str
    name: str
    gender: Optional[str] = None
    price: Decimal
    color: str
    fabric: Optional[str] = None
    description: Optional[str] = None
    sizes: List[str] = Field(default_factory=list)
    stock_count: int = 0
    image_urls: List[str] = Field(default_factory=list)
    video_urls: List[str] = Field(default_factory=list)

class ProductCreate(ProductBase):
    category_name: Optional[str] = None

class ProductUpdate(BaseModel):
    category_name: Optional[str] = None
    sku: Optional[str] = None
    name: Optional[str] = None
    gender: Optional[str] = None
    price: Optional[Decimal] = None
    color: Optional[str] = None
    fabric: Optional[str] = None
    description: Optional[str] = None
    sizes: Optional[List[str]] = None
    stock_count: Optional[int] = None
    image_urls: Optional[List[str]] = None
    video_urls: Optional[List[str]] = None

class ProductOut(ProductBase):
    id: UUID
    organization_id: UUID
    category_id: Optional[UUID] = None
    embedding_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Message
class MessageBase(BaseModel):
    sender: str  # 'customer', 'ai', 'human'
    message_type: str  # 'text', 'image', 'video', 'interactive'
    content: str
    media_url: Optional[str] = None

class MessageOut(MessageBase):
    id: UUID
    conversation_id: UUID
    status: str
    error_message: Optional[str] = None
    detected_language: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MessageCreate(BaseModel):
    content: str


# Conversation
class ConversationBase(BaseModel):
    customer_phone: str
    customer_name: Optional[str] = None
    status: str  # 'AI_ACTIVE', 'WAITING_APPROVAL', 'OWNER_ACTIVE', 'CLOSED'
    assigned_user_id: Optional[UUID] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_", serialization_alias="metadata")
    lead_score: Optional[int] = 0
    escalation_reason: Optional[str] = None

class ConversationOut(ConversationBase):
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ConversationDetail(ConversationOut):
    messages: List[MessageOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# Customer Memory
class CustomerMemoryBase(BaseModel):
    customer_phone: str
    preferred_sizes: List[str] = Field(default_factory=list)
    preferred_colors: List[str] = Field(default_factory=list)
    preferred_fabrics: List[str] = Field(default_factory=list)
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    style_notes: Optional[str] = None
    total_purchases: int = 0
    total_spent: Decimal = Decimal('0.00')

class CustomerMemoryOut(CustomerMemoryBase):
    id: UUID
    organization_id: UUID
    last_interaction: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Order Item
class OrderItemBase(BaseModel):
    product_name: str
    product_sku: str
    quantity: int = 1
    unit_price: Decimal
    selected_size: Optional[str] = None

class OrderItemCreate(OrderItemBase):
    product_id: Optional[UUID] = None

class OrderItemOut(OrderItemBase):
    id: UUID
    order_id: UUID
    product_id: Optional[UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Order
class OrderBase(BaseModel):
    customer_phone: str
    status: str = "pending"
    payment_method: Optional[str] = None
    payment_id: Optional[str] = None
    total_amount: Decimal
    shipping_address: Optional[str] = None
    notes: Optional[str] = None

class OrderCreate(OrderBase):
    conversation_id: Optional[UUID] = None
    items: List[OrderItemCreate] = Field(default_factory=list)

class OrderOut(OrderBase):
    id: UUID
    organization_id: UUID
    conversation_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# Recommendation Feedback
class RecommendationFeedbackCreate(BaseModel):
    message_id: UUID
    product_sku: str
    rating: int  # 1 or -1
    reason: Optional[str] = None

class RecommendationFeedbackOut(BaseModel):
    id: UUID
    message_id: UUID
    product_sku: str
    rating: int
    reason: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Approval Request
class ApprovalRequestOut(BaseModel):
    id: UUID
    conversation_id: UUID
    organization_id: UUID
    status: str
    reason: str
    proposed_response: str
    ai_recommendation: Optional[str] = None
    risk_score: int
    llm_model: Optional[str] = None
    prompt_version: Optional[str] = None
    retrieval_ids: List[str] = Field(default_factory=list)
    grounding_score: Decimal = Decimal('0.00')
    decision_engine_version: Optional[str] = None
    rule_triggered: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_", serialization_alias="metadata")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApprovalRequestRespond(BaseModel):
    action: str  # 'approve', 'reject', 'edit'
    edited_response: Optional[str] = None


# Notification
class NotificationBase(BaseModel):
    type: str
    status: str = "unread"

class NotificationOut(NotificationBase):
    id: UUID
    organization_id: UUID
    approval_request_id: Optional[UUID] = None
    created_at: datetime
    read_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
