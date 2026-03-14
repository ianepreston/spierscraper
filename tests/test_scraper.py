"""Tests for the scraper module."""

from decimal import Decimal

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

    def test_extract_options_from_html(self):
        scraper = SpierMackayScraper()

        html = """
        <div data-option-name="fit">
            <button>Slim</button>
            <button>Contemporary</button>
        </div>
        <div data-option-name="size">
            <button>32</button>
            <button>33</button>
            <button>34</button>
        </div>
        """
        tree = HTMLParser(html)

        fits = scraper._extract_options(tree, "fit")
        sizes = scraper._extract_options(tree, "size")

        assert fits == ["Slim", "Contemporary"]
        assert sizes == ["32", "33", "34"]

    def test_parse_product_card(self, sample_products_html: str):
        scraper = SpierMackayScraper()
        tree = HTMLParser(sample_products_html)

        cards = tree.css(".product-card")
        assert len(cards) == 2

        product = scraper._parse_product_card(cards[0], "clearance-rack")
        assert product is not None
        assert product["name"] == "Brown Chino"
        assert product["price"] == Decimal("24.99")
        assert product["original_price"] == Decimal("68.00")
        assert "product/brown-chino" in product["url"]

    def test_parse_product_card_no_link(self):
        scraper = SpierMackayScraper()
        html = "<div class='product-card'><span>No link here</span></div>"
        tree = HTMLParser(html)
        card = tree.css_first(".product-card")

        result = scraper._parse_product_card(card, "test")
        assert result is None

    def test_get_headers_rotates_user_agent(self):
        scraper = SpierMackayScraper()

        headers1 = scraper._get_headers()
        headers2 = scraper._get_headers()
        _headers3 = scraper._get_headers()

        # Should cycle through user agents
        assert headers1["User-Agent"] != headers2["User-Agent"]
        # After 3 calls, should wrap around to first
        assert headers1["User-Agent"] == scraper._get_headers()["User-Agent"]
