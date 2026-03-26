"""Tests for filtering logic."""

from decimal import Decimal

import pytest

from spierscraper.config import Config
from spierscraper.filters import categorize_product, filter_products, matches_filter
from spierscraper.models import GarmentCategory, Product, ProductVariant


class TestCategorizeProduct:
    """Tests for product categorization."""

    @pytest.mark.parametrize(
        "name,collection,expected",
        [
            ("Brown Chino", "clearance-rack", GarmentCategory.CHINOS),
            ("Navy Trousers", "odds-ends-trousers", GarmentCategory.PANTS),
            ("Gray Flannel Trousers", "clearance-rack", GarmentCategory.PANTS),
            ("Blue Sport Coat", "clearance-sport-coats", GarmentCategory.SPORT_COATS),
            ("Navy Blazer Sportcoat", "clearance-rack", GarmentCategory.SPORT_COATS),
            ("White Dress Shirt", "clearance-shirts", GarmentCategory.SHIRTS),
            ("Merino Sweater", "clearance-rack", GarmentCategory.KNITWEAR),
            ("Wool Cardigan", "odds-ends-knitwear", GarmentCategory.KNITWEAR),
            ("Navy Suit", "clearance-suits", GarmentCategory.SUITS),
            ("Random Item", "clearance-rack", GarmentCategory.OTHER),
        ],
    )
    def test_categorize_product(self, name: str, collection: str, expected: GarmentCategory):
        result = categorize_product(name, collection)
        assert result == expected


class TestMatchesFilter:
    """Tests for variant matching logic."""

    def test_matches_with_fit_and_size(self):
        variant = ProductVariant(fit="Contemporary", size="33", sku="test-123", in_stock=True)
        assert matches_filter(variant, ["Contemporary"], ["33"]) is True
        assert matches_filter(variant, ["Slim"], ["33"]) is False
        assert matches_filter(variant, ["Contemporary"], ["34"]) is False

    def test_matches_partial_fit_name(self):
        variant = ProductVariant(
            fit="Moro Cut (Regular)", size="40R", sku="test-123", in_stock=True
        )
        # Should match partial names
        assert matches_filter(variant, ["Moro"], ["40R"]) is True
        assert matches_filter(variant, ["Moro Cut"], ["40R"]) is True

    def test_empty_filter_matches_all(self):
        variant = ProductVariant(fit="Any Fit", size="Any Size", sku="test-123", in_stock=True)
        assert matches_filter(variant, [], []) is True
        assert matches_filter(variant, ["Any Fit"], []) is True
        assert matches_filter(variant, [], ["Any Size"]) is True


class TestFilterProducts:
    """Tests for product filtering."""

    def test_filters_by_category(self, sample_config: Config):
        products = [
            Product(
                name="Brown Chino",
                url="http://example.com/chino",
                sku="CHN-123",
                price=Decimal("25.00"),
                category=GarmentCategory.CHINOS,
                collection="clearance",
                variants=[
                    ProductVariant(
                        fit="Contemporary", size="33", sku="CHN-123-C-33", in_stock=True
                    ),
                ],
            ),
            Product(
                name="Random Shirt",
                url="http://example.com/shirt",
                sku="SHT-456",
                price=Decimal("20.00"),
                category=GarmentCategory.SHIRTS,
                collection="clearance",
                variants=[
                    ProductVariant(fit="Slim", size="15", sku="SHT-456-S-15", in_stock=True),
                ],
            ),
        ]

        matches = filter_products(products, sample_config)

        # Should match chinos but not shirts (no filter defined)
        assert len(matches) == 1
        assert matches[0].product.name == "Brown Chino"

    def test_filters_out_of_stock(self, sample_config: Config):
        products = [
            Product(
                name="Brown Chino",
                url="http://example.com/chino",
                sku="CHN-123",
                price=Decimal("25.00"),
                category=GarmentCategory.CHINOS,
                collection="clearance",
                variants=[
                    ProductVariant(
                        fit="Contemporary", size="33", sku="CHN-123-C-33", in_stock=False
                    ),
                    ProductVariant(
                        fit="Contemporary", size="34", sku="CHN-123-C-34", in_stock=True
                    ),
                ],
            ),
        ]

        matches = filter_products(products, sample_config)

        # Should only include in-stock variant
        assert len(matches) == 1
        assert len(matches[0].matching_variants) == 1
        assert matches[0].matching_variants[0].size == "34"

    def test_no_matches_returns_empty(self, sample_config: Config):
        products = [
            Product(
                name="Brown Chino",
                url="http://example.com/chino",
                sku="CHN-123",
                price=Decimal("25.00"),
                category=GarmentCategory.CHINOS,
                collection="clearance",
                variants=[
                    ProductVariant(fit="Extra Slim", size="30", sku="CHN-123-ES-30", in_stock=True),
                ],
            ),
        ]

        matches = filter_products(products, sample_config)
        assert len(matches) == 0
