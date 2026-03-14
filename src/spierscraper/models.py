"""Data models for products and variants."""

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class GarmentCategory(StrEnum):
    """Known garment categories with distinct fit/size schemes."""

    PANTS = "pants"
    CHINOS = "chinos"
    SPORT_COATS = "sport_coats"
    SUITS = "suits"
    SHIRTS = "shirts"
    KNITWEAR = "knitwear"
    OUTERWEAR = "outerwear"
    OTHER = "other"


class ProductVariant(BaseModel):
    """A specific fit/size combination for a product."""

    fit: str
    size: str
    sku: str
    in_stock: bool
    quantity: int | None = None


class Product(BaseModel):
    """A product listing from the site."""

    name: str
    url: str
    sku: str
    price: Decimal
    original_price: Decimal | None = None
    category: GarmentCategory
    collection: str
    variants: list[ProductVariant] = Field(default_factory=list)

    @property
    def discount_percent(self) -> int | None:
        """Calculate discount percentage if original price exists."""
        if self.original_price and self.original_price > 0:
            discount = (self.original_price - self.price) / self.original_price * 100
            return int(discount)
        return None

    @property
    def in_stock_variants(self) -> list[ProductVariant]:
        """Return only variants that are in stock."""
        return [v for v in self.variants if v.in_stock]


class ProductMatch(BaseModel):
    """A product that matched the user's filter criteria."""

    product: Product
    matching_variants: list[ProductVariant]

    @property
    def is_new(self) -> bool:
        """Whether this match is new (not seen before)."""
        # Set by cache comparison
        return getattr(self, "_is_new", True)
