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
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MessageCreate(BaseModel):
    content: str


# Conversation
class ConversationBase(BaseModel):
    customer_phone: str
    customer_name: Optional[str] = None
    status: str  # 'ai_active', 'human_takeover', 'resolved'
    assigned_user_id: Optional[UUID] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_", serialization_alias="metadata")

class ConversationOut(ConversationBase):
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ConversationDetail(ConversationOut):
    messages: List[MessageOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
