"""Tests for the match cache."""

import time
from decimal import Decimal

import pytest

from spierscraper.cache import MatchCache
from spierscraper.models import GarmentCategory, Product, ProductMatch, ProductVariant


@pytest.fixture
def sample_match() -> ProductMatch:
    """Create a sample product match for testing."""
    product = Product(
        name="Test Product",
        url="http://example.com/product",
        sku="TEST-123",
        price=Decimal("50.00"),
        category=GarmentCategory.PANTS,
        collection="clearance",
        variants=[
            ProductVariant(fit="Slim", size="33", sku="TEST-123-S-33", in_stock=True, quantity=2),
        ],
    )
    return ProductMatch(
        product=product,
        matching_variants=product.variants,
    )


class TestMatchCache:
    """Tests for MatchCache."""

    def test_new_match_is_new(self, sample_match: ProductMatch):
        cache = MatchCache(ttl_hours=24)

        assert cache.is_new(sample_match) is True

    def test_seen_match_is_not_new(self, sample_match: ProductMatch):
        cache = MatchCache(ttl_hours=24)

        cache.mark_seen(sample_match)
        assert cache.is_new(sample_match) is False

    def test_expired_match_is_new(self, sample_match: ProductMatch):
        # Use 0 TTL for immediate expiry
        cache = MatchCache(ttl_hours=0)
        cache.ttl_seconds = 0  # Override for test

        cache.mark_seen(sample_match)
        time.sleep(0.01)  # Small delay
        assert cache.is_new(sample_match) is True

    def test_filter_new_returns_only_new(self):
        cache = MatchCache(ttl_hours=24)

        matches = []
        for i in range(3):
            product = Product(
                name=f"Product {i}",
                url=f"http://example.com/{i}",
                sku=f"SKU-{i}",
                price=Decimal("50.00"),
                category=GarmentCategory.PANTS,
                collection="clearance",
                variants=[
                    ProductVariant(
                        fit="Slim", size="33", sku=f"SKU-{i}-S-33", in_stock=True
                    ),
                ],
            )
            matches.append(ProductMatch(product=product, matching_variants=product.variants))

        # Mark first one as seen
        cache.mark_seen(matches[0])

        # Filter should return only the new ones
        new_matches = cache.filter_new(matches)
        assert len(new_matches) == 2
        assert matches[0] not in new_matches

    def test_different_stock_is_new(self, sample_match: ProductMatch):
        cache = MatchCache(ttl_hours=24)

        cache.mark_seen(sample_match)

        # Same product but different stock quantity = new key
        product2 = Product(
            name="Test Product",
            url="http://example.com/product",
            sku="TEST-123",
            price=Decimal("50.00"),
            category=GarmentCategory.PANTS,
            collection="clearance",
            variants=[
                ProductVariant(
                    fit="Slim", size="33", sku="TEST-123-S-33", in_stock=True, quantity=5
                ),
            ],
        )
        match2 = ProductMatch(product=product2, matching_variants=product2.variants)

        # Different quantity = different hash = new match
        assert cache.is_new(match2) is True
