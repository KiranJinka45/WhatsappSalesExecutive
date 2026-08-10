from pydantic import BaseModel, Field, field_validator, ValidationError
from decimal import Decimal
from typing import List

class CatalogRow(BaseModel):
    sku: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    price: Decimal = Field(..., ge=0)
    color: str = Field(..., min_length=1)
    category_name: str = Field(..., min_length=2, max_length=50)
    gender: str = Field(default="Unisex")
    fabric: str = Field(..., min_length=1)
    description: str = Field(default="")
    stock_count: int = Field(..., ge=0)
    sizes: List[str] = Field(default_factory=list)
    image_urls: List[str] = Field(default_factory=list)
    video_urls: List[str] = Field(default_factory=list)

    @field_validator("image_urls", "video_urls", mode="before")
    def split_urls(cls, v):
        if isinstance(v, str):
            return [url.strip() for url in v.split(",") if url.strip()]
        return v

    @field_validator("sizes", mode="before")
    def split_sizes(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

try:
    row = CatalogRow(
        sku="123", name="test", price="100.0", color="red", category_name="cat", 
        fabric="cotton", stock_count="10"
    )
    print("Success:", row)
except ValidationError as e:
    print("Error:", e)
