"""Filtering logic for matching products to user criteria."""

from .config import Config
from .models import GarmentCategory, Product, ProductMatch, ProductVariant


def categorize_product(product_name: str, collection: str) -> GarmentCategory:
    """Determine the garment category from product name and collection."""
    name_lower = product_name.lower()
    collection_lower = collection.lower()

    # Check collection first for more specific matching
    if "trouser" in collection_lower or "trouser" in name_lower:
        return GarmentCategory.PANTS
    if "chino" in collection_lower or "chino" in name_lower:
        return GarmentCategory.CHINOS
    if "sport" in collection_lower and "coat" in collection_lower:
        return GarmentCategory.SPORT_COATS
    if "sportcoat" in name_lower or "sport coat" in name_lower:
        return GarmentCategory.SPORT_COATS
    if "suit" in collection_lower or "suit" in name_lower:
        return GarmentCategory.SUITS
    if "shirt" in collection_lower or "shirt" in name_lower:
        return GarmentCategory.SHIRTS
    if "knit" in collection_lower or "sweater" in name_lower or "cardigan" in name_lower:
        return GarmentCategory.KNITWEAR
    if "coat" in name_lower or "jacket" in name_lower or "outerwear" in collection_lower:
        return GarmentCategory.OUTERWEAR
    if "pant" in name_lower:
        return GarmentCategory.PANTS

    return GarmentCategory.OTHER


def matches_filter(variant: ProductVariant, fits: list[str], sizes: list[str]) -> bool:
    """Check if a variant matches the filter criteria."""
    fit_match = not fits or any(
        f.lower() in variant.fit.lower() or variant.fit.lower() in f.lower() for f in fits
    )
    size_match = not sizes or variant.size in sizes

    return fit_match and size_match


def filter_products(products: list[Product], config: Config) -> list[ProductMatch]:
    """Filter products based on configuration criteria.

    Returns only products that:
    1. Have a category with defined filters
    2. Have at least one in-stock variant matching the fit/size criteria
    """
    matches: list[ProductMatch] = []

    for product in products:
        category_filter = config.get_filter(product.category.value)

        # Skip categories without filters (user not interested)
        if category_filter is None:
            continue

        # Find variants matching the criteria
        matching_variants = [
            v
            for v in product.in_stock_variants
            if matches_filter(v, category_filter.fits, category_filter.sizes)
        ]

        if matching_variants:
            matches.append(
                ProductMatch(
                    product=product,
                    matching_variants=matching_variants,
                )
            )

    return matches
