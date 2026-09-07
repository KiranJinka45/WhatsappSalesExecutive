from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal


StructuredIntentType = Literal[
    "product_search",
    "stock_inquiry",
    "bargaining",
    "bulk_order",
    "complaint",
    "refund",
    "shipping_exception",
    "general_faq",
    "order_status",
    "product_visual_search"
]


class ProductSearchCriteria(BaseModel):
    """
    Structured extraction of customer product preferences for deterministic SQL catalog querying.
    """
    product_type: Optional[str] = Field(None, description="Type of apparel, e.g. Saree, Kurti, Lehenga, Dress")
    color: Optional[str] = Field(None, description="Color preference, e.g. Maroon, Blue, Gold, Green")
    fabric: Optional[str] = Field(None, description="Fabric material, e.g. Silk, Cotton, Kanjeevaram, Banarasi, Georgette")
    size: Optional[str] = Field(None, description="Size, e.g. S, M, L, XL, XXL, Free Size")
    budget_min: Optional[float] = Field(None, ge=0, description="Minimum price in INR")
    budget_max: Optional[float] = Field(None, ge=0, description="Maximum price in INR (e.g. 'under 4000')")
    gender: Optional[str] = Field(None, description="Target gender, e.g. Women, Men, Kids")
    keywords: List[str] = Field(default_factory=list, description="Specific style keywords or product names")
    is_in_stock_only: bool = Field(default=True, description="Whether to filter out-of-stock items")

    model_config = ConfigDict(extra="ignore")


class IntentExtraction(BaseModel):
    """
    Output model for Layer 1 LLM Intent Router and Structured Information Extraction.
    """
    intent: StructuredIntentType = Field(
        ..., 
        description="Classified commerce intent for the incoming customer message"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0")
    explanation: Optional[str] = Field(None, description="Brief explanation for the classified intent")
    
    # Structured entities depending on intent
    product_search: Optional[ProductSearchCriteria] = Field(
        None, 
        description="Extracted product search criteria if the intent is product_search, stock_inquiry, or product_visual_search"
    )
    order_reference: Optional[str] = Field(None, description="Order ID or tracking number if referenced")
    discount_requested_pct: Optional[float] = Field(None, ge=0, le=100, description="Discount percentage asked if bargaining")
    target_price: Optional[float] = Field(None, ge=0, description="Target haggled price offered by customer")
    quantity_requested: Optional[int] = Field(None, ge=1, description="Quantity requested if bulk order inquiry")

    model_config = ConfigDict(extra="ignore")


class GroundedProductResult(BaseModel):
    """
    Deterministic catalog product fact returned by SQL execution (Layer 2).
    """
    id: str
    sku: str
    name: str
    price: float
    stock_count: int
    color: Optional[str] = None
    fabric: Optional[str] = None
    category: Optional[str] = None
    sizes: List[str] = Field(default_factory=list)
    image_urls: List[str] = Field(default_factory=list)
    description: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class DraftGenerationResult(BaseModel):
    """
    Output of Layer 3 Grounded Draft Generation.
    """
    intent_extraction: IntentExtraction
    retrieved_products: List[GroundedProductResult] = Field(default_factory=list)
    price_snapshot: Dict[str, float] = Field(default_factory=dict)
    stock_snapshot: Dict[str, int] = Field(default_factory=dict)
    proposed_response: str
    grounding_score: float = 1.0
    action: str = "wait_for_approval"
    escalation_reason: Optional[str] = None
    risk_score: int = 0
    ai_recommendation: str = "approve"
    rule_triggered: Optional[str] = None
    detected_language: str = "en"
    detected_script: str = "latin"

    model_config = ConfigDict(extra="ignore")
