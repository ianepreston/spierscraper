"""Tests for the scraper module."""

from decimal import Decimal

import pytest
import respx
from httpx import Response
from selectolax.parser import HTMLParser

from spierscraper.scraper import SpierMackayScraper


class TestSpierMackayScraper:
    """Tests for SpierMackayScraper."""

    def test_parse_price(self):
        scraper = SpierMackayScraper()

        assert scraper._parse_price("$24.99") == Decimal("24.99")
        assert scraper._parse_price("$1,234.56") == Decimal("1234.56")
        assert scraper._parse_price("CAD $99.00") == Decimal("99.00")
        assert scraper._parse_price("") == Decimal("0")
        assert scraper._parse_price("invalid") == Decimal("0")

    def test_parse_option_groups_from_html(self):
        """Test parsing fit/size options with option_id and option_value_id."""
        scraper = SpierMackayScraper()

        # HTML structure matches actual site - both use size1 class,
        # distinguished by option_id and section title
        html = """
        <div id="option_product_details">
            <div class="title-wrapper">
                <div class="modal-title1">Chinos - Fit</div>
            </div>
            <div class="collar-options">
                <label class="size1" option_id="883" option_value_id="1530">
                    <span>Extra Slim</span>
                </label>
                <label class="size1" option_id="883" option_value_id="1531">
                    <span>Slim</span>
                </label>
                <label class="size1" option_id="883" option_value_id="1532">
                    <span>Contemporary</span>
                </label>
            </div>
            <div class="title-wrapper">
                <div class="modal-title1">Chinos - Size</div>
            </div>
            <div class="collar-options">
                <label class="size1" option_id="878" option_value_id="1512">
                    <span>33</span>
                </label>
                <label class="size1" option_id="878" option_value_id="1513">
                    <span>34</span>
                </label>
            </div>
        </div>
        """
        tree = HTMLParser(html)
        container = tree.css_first("#option_product_details")

        fits, sizes = scraper._parse_option_groups(container)

        assert len(fits) == 3
        assert fits[0].name == "Extra Slim"
        assert fits[0].option_id == "883"
        assert fits[0].option_value_id == "1530"
        assert fits[2].name == "Contemporary"

        assert len(sizes) == 2
        assert sizes[0].name == "33"
        assert sizes[0].option_id == "878"
        assert sizes[0].option_value_id == "1512"

    def test_parse_product_card(self, sample_products_html: str):
        """Test parsing product cards with actual site HTML structure."""
        scraper = SpierMackayScraper()
        tree = HTMLParser(sample_products_html)

        # Site uses .item-product class for product cards
        cards = tree.css(".item-product")
        assert len(cards) == 2

        product = scraper._parse_product_card(cards[0], "clearance-rack")
        assert product is not None
        assert product["name"] == "Brown Chino"
        assert product["price"] == Decimal("24.99")
        assert product["original_price"] == Decimal("68.00")
        assert "product/brown-chino" in product["url"]

    def test_parse_product_card_no_link(self):
        scraper = SpierMackayScraper()
        html = "<div class='item-product'><span>No link here</span></div>"
        tree = HTMLParser(html)
        card = tree.css_first(".item-product")

        result = scraper._parse_product_card(card, "test")
        assert result is None

    def test_parse_products_html_from_api_response(self, sample_api_response: dict):
        """Test parsing HTML products from the collection API JSON response.

        The API returns JSON with HTML in the 'products' field, not a list.
        This test ensures we correctly parse this HTML structure.
        """
        scraper = SpierMackayScraper()
        products_html = sample_api_response["products"]

        products = scraper._parse_products_html(products_html, "sale-shirts")

        assert len(products) == 2
        assert products[0]["name"] == "Cream Birdseye Dress Shirt - Final Sale"
        assert products[0]["price"] == Decimal("24.99")
        assert products[0]["original_price"] == Decimal("68.00")
        # SKU is extracted from end of URL path
        assert products[0]["sku"]  # Has some SKU value
        assert products[1]["name"] == "Navy Stripe Trousers"
        assert products[1]["price"] == Decimal("49.99")

    def test_parse_products_html_empty(self):
        """Test that empty HTML returns empty list."""
        scraper = SpierMackayScraper()

        assert scraper._parse_products_html("", "test") == []
        assert scraper._parse_products_html("<div></div>", "test") == []

    def test_parse_products_html_extracts_sku_from_url(self):
        """Test that SKU is correctly extracted from product URL."""
        scraper = SpierMackayScraper()
        html = """
        <div class="item-product">
            <a href="/product/cream-dress-shirt-11081-c7f5k">
                <div class="prod-name">Test Shirt</div>
                <div class="prod-price">$24.99</div>
            </a>
        </div>
        """
        products = scraper._parse_products_html(html, "test")

        assert len(products) == 1
        # SKU is extracted from the last segment of URL and uppercased
        assert products[0]["sku"] == "C7F5K"

    def test_get_headers_rotates_user_agent(self):
        scraper = SpierMackayScraper()

        headers1 = scraper._get_headers()
        headers2 = scraper._get_headers()
        _headers3 = scraper._get_headers()

        # Should cycle through user agents
        assert headers1["User-Agent"] != headers2["User-Agent"]
        # After 3 calls, should wrap around to first
        assert headers1["User-Agent"] == scraper._get_headers()["User-Agent"]


@pytest.mark.asyncio
class TestCollectionAPI:
    """Tests for collection API integration.

    These tests verify the correct API parameters and headers are used,
    which was a bug that prevented products from being found.
    """

    @respx.mock
    async def test_fetch_collection_uses_page_no_parameter(self, sample_api_response: dict):
        """Test that API uses 'page_no' parameter, not 'page'.

        Bug fix: The API requires 'page_no' parameter. Using 'page' returns HTML
        instead of JSON, causing the scraper to fall back to HTML scraping which
        used wrong selectors.
        """
        route = respx.get(
            "https://www.spierandmackay.com/Category/collection_view/sale-shirts"
        ).mock(return_value=Response(200, json=sample_api_response))

        async with SpierMackayScraper(rate_limit=0) as scraper:
            await scraper.fetch_collection_products("sale-shirts")

        # Verify the correct parameter was used
        assert route.called
        request = route.calls[0].request
        assert "page_no=1" in str(request.url)
        assert "page=" not in str(request.url).replace("page_no", "")

    @respx.mock
    async def test_fetch_collection_sends_xhr_header(self, sample_api_response: dict):
        """Test that API sends X-Requested-With header for JSON response.

        Bug fix: Without this header, the API returns HTML instead of JSON.
        """
        route = respx.get(
            "https://www.spierandmackay.com/Category/collection_view/sale-shirts"
        ).mock(return_value=Response(200, json=sample_api_response))

        async with SpierMackayScraper(rate_limit=0) as scraper:
            await scraper.fetch_collection_products("sale-shirts")

        assert route.called
        request = route.calls[0].request
        assert request.headers.get("X-Requested-With") == "XMLHttpRequest"

    @respx.mock
    async def test_fetch_collection_paginates_correctly(self):
        """Test that pagination uses page_no from response."""
        page1_response = {
            "status": True,
            "products": """
                <div class="item-product">
                    <a href="/product/test-product-123">
                        <div class="prod-name">Product 1</div>
                        <div class="prod-price">$24.99</div>
                    </a>
                </div>
            """,
            "page_no": 2,  # Next page is 2
        }
        page2_response = {
            "status": True,
            "products": "",  # Empty = no more products
            "page_no": 2,
        }

        route = respx.get(
            "https://www.spierandmackay.com/Category/collection_view/test-collection"
        ).mock(side_effect=[Response(200, json=page1_response), Response(200, json=page2_response)])

        async with SpierMackayScraper(rate_limit=0) as scraper:
            products = await scraper.fetch_collection_products("test-collection")

        # Should have fetched 2 pages
        assert route.call_count == 2
        # First call should use page_no=1
        assert "page_no=1" in str(route.calls[0].request.url)
        # Second call should use page_no=2 (from response)
        assert "page_no=2" in str(route.calls[1].request.url)
        # Should have parsed 1 product from page 1
        assert len(products) == 1
