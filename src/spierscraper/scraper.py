"""Core scraping engine for Spier & Mackay website."""

import asyncio
import logging
import re
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser, Node
from tenacity import retry, stop_after_attempt, wait_exponential

from .filters import categorize_product
from .models import Product, ProductVariant

logger = logging.getLogger(__name__)

# Collections to auto-discover from navigation
CLEARANCE_KEYWORDS = ["clearance", "odds", "ends", "sale"]

# User agent rotation - fmt: off
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0",
]


class SpierMackayScraper:
    """Scraper for Spier & Mackay clearance and odds/ends sections."""

    def __init__(
        self,
        base_url: str = "https://www.spierandmackay.com",
        rate_limit: float = 1.5,
    ):
        self.base_url = base_url.rstrip("/")
        self.rate_limit = rate_limit
        self._ua_index = 0
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "SpierMackayScraper":
        self._client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
            headers=self._get_headers(),
        )
        return self

    async def __aexit__(self, *args: object) -> None:
        if self._client:
            await self._client.aclose()

    def _get_headers(self) -> dict[str, str]:
        ua = USER_AGENTS[self._ua_index % len(USER_AGENTS)]
        self._ua_index += 1
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

    async def _rate_limit_delay(self) -> None:
        await asyncio.sleep(self.rate_limit)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _fetch(self, url: str, **kwargs: Any) -> httpx.Response:
        """Fetch URL with retry logic."""
        if not self._client:
            raise RuntimeError("Scraper not initialized. Use async with.")

        await self._rate_limit_delay()
        response = await self._client.get(url, **kwargs)
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _post(self, url: str, **kwargs: Any) -> httpx.Response:
        """POST request with retry logic."""
        if not self._client:
            raise RuntimeError("Scraper not initialized. Use async with.")

        await self._rate_limit_delay()
        response = await self._client.post(url, **kwargs)
        response.raise_for_status()
        return response

    async def discover_clearance_collections(self) -> list[str]:
        """Auto-discover clearance and odds/ends collection slugs from nav."""
        logger.info("Discovering clearance collections...")

        response = await self._fetch(self.base_url)
        tree = HTMLParser(response.text)

        collections: set[str] = set()

        # Find all collection links in navigation
        for link in tree.css("a[href*='/collection/']"):
            href = link.attributes.get("href") or ""
            text = link.text(strip=True).lower()

            # Extract slug from URL
            match = re.search(r"/collection/([^/?#]+)", str(href))
            if not match:
                continue

            slug = match.group(1)

            # Check if it's a clearance/sale collection
            if any(kw in slug.lower() or kw in text for kw in CLEARANCE_KEYWORDS):
                collections.add(slug)
                logger.debug(f"Found collection: {slug}")

        logger.info(f"Discovered {len(collections)} clearance collections")
        return sorted(collections)

    async def fetch_collection_products(self, collection_slug: str) -> list[dict[str, Any]]:
        """Fetch all products from a collection using the AJAX API."""
        logger.info(f"Fetching collection: {collection_slug}")

        products: list[dict[str, Any]] = []
        page = 1

        while True:
            # The site uses a PHP backend with this endpoint pattern
            url = f"{self.base_url}/Category/collection_view/{collection_slug}"
            params = {"page": page}

            try:
                response = await self._fetch(url, params=params)
                data = response.json()

                # Check if we got products
                if not data.get("products"):
                    break

                products.extend(data["products"])
                logger.debug(f"Page {page}: {len(data['products'])} products")

                # Check for more pages
                if not data.get("has_more", False):
                    break

                page += 1

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    break
                raise
            except Exception:
                # Fall back to HTML scraping
                logger.debug(f"API failed for {collection_slug}, trying HTML")
                return await self._fetch_collection_html(collection_slug)

        logger.info(f"Collection {collection_slug}: {len(products)} products total")
        return products

    async def _fetch_collection_html(self, collection_slug: str) -> list[dict[str, Any]]:
        """Fallback: scrape collection page HTML."""
        url = f"{self.base_url}/collection/{collection_slug}"
        response = await self._fetch(url)
        tree = HTMLParser(response.text)

        products: list[dict[str, Any]] = []

        # Find product cards
        for card in tree.css(".product-card, .product-item, [data-product-id]"):
            product_data = self._parse_product_card(card, collection_slug)
            if product_data:
                products.append(product_data)

        return products

    def _parse_product_card(self, card: Node, collection_slug: str) -> dict[str, Any] | None:
        """Parse a product card HTML element."""
        # Try to find product link
        link = card.css_first("a[href*='/product/']")
        if not link:
            return None

        href = link.attributes.get("href") or ""
        url = urljoin(self.base_url, str(href))

        # Extract SKU from URL
        sku_match = re.search(r"/product/[^/]+-([a-z0-9-]+)$", str(href), re.I)
        sku = sku_match.group(1) if sku_match else ""

        # Product name
        name_el = card.css_first(".product-name, .product-title, h3, h4")
        name = name_el.text(strip=True) if name_el else "Unknown"

        # Price
        price_el = card.css_first(".sale-price, .price, .product-price")
        price_text = price_el.text(strip=True) if price_el else "$0"
        price = self._parse_price(price_text)

        # Original price
        orig_el = card.css_first(".original-price, .was-price, .compare-price")
        original_price = self._parse_price(orig_el.text(strip=True)) if orig_el else None

        return {
            "name": name,
            "url": url,
            "sku": sku,
            "price": price,
            "original_price": original_price,
            "collection": collection_slug,
        }

    def _parse_price(self, text: str) -> Decimal:
        """Parse price string to Decimal."""
        # Remove currency symbols and whitespace
        cleaned = re.sub(r"[^\d.]", "", text)
        try:
            return Decimal(cleaned)
        except Exception:
            return Decimal("0")

    async def fetch_product_details(self, product_url: str) -> dict[str, Any]:
        """Fetch detailed product info including variants and stock."""
        response = await self._fetch(product_url)
        tree = HTMLParser(response.text)


        # Find variant options (fit/size selectors)
        # The site typically has these as button groups or select elements
        fits = self._extract_options(tree, "fit")
        sizes = self._extract_options(tree, "size")

        # Extract SKU base
        sku_el = tree.css_first("[data-sku], .sku, .product-sku")
        base_sku = sku_el.text(strip=True) if sku_el else ""

        # For each combination, we need to check stock
        # This will be done via API call
        return {
            "fits": fits,
            "sizes": sizes,
            "base_sku": base_sku,
        }

    def _extract_options(self, tree: HTMLParser, option_type: str) -> list[str]:
        """Extract fit or size options from product page."""
        options: list[str] = []

        # Try various selectors
        selectors = [
            f"[data-option-name*='{option_type}' i] button",
            f"[data-option-name*='{option_type}' i] .option",
            f".{option_type}-options button",
            f".{option_type}-selector option",
            f"[class*='{option_type}'] button",
        ]

        for selector in selectors:
            for el in tree.css(selector):
                text = el.text(strip=True)
                if text and text not in options:
                    options.append(text)

            if options:
                break

        return options

    async def fetch_stock_levels(self, sku: str) -> dict[str, int]:
        """Fetch stock quantities for a SKU via API."""
        url = f"{self.base_url}/Product/get_sku_qty"

        try:
            response = await self._post(url, data={"sku": sku})
            data = response.json()

            if isinstance(data, dict):
                return {k: int(v) for k, v in data.items() if str(v).isdigit()}
        except Exception as e:
            logger.warning(f"Failed to fetch stock for {sku}: {e}")

        return {}

    async def scrape_all(self) -> list[Product]:
        """Main entry point: discover and scrape all clearance products."""
        collections = await self.discover_clearance_collections()

        if not collections:
            logger.warning("No clearance collections found")
            return []

        all_products: list[Product] = []

        for slug in collections:
            try:
                raw_products = await self.fetch_collection_products(slug)

                for raw in raw_products:
                    product = await self._build_product(raw, slug)
                    if product:
                        all_products.append(product)

            except Exception as e:
                logger.error(f"Failed to scrape collection {slug}: {e}")
                continue

        logger.info(f"Total products scraped: {len(all_products)}")
        return all_products

    async def _build_product(self, raw: dict[str, Any], collection: str) -> Product | None:
        """Build a Product model from raw scraped data."""
        try:
            # Get category from name/collection
            category = categorize_product(raw.get("name", ""), collection)

            # Fetch variants and stock
            variants: list[ProductVariant] = []
            if raw.get("url"):
                details = await self.fetch_product_details(raw["url"])

                # Build variant combinations
                for fit in details.get("fits", [""]) or [""]:
                    for size in details.get("sizes", [""]) or [""]:
                        variant_sku = f"{raw.get('sku', '')}-{fit}-{size}".strip("-")

                        # Check stock
                        stock_data = await self.fetch_stock_levels(variant_sku)
                        qty = stock_data.get(variant_sku, 0)

                        variants.append(
                            ProductVariant(
                                fit=fit or "Standard",
                                size=size or "One Size",
                                sku=variant_sku,
                                in_stock=qty > 0,
                                quantity=qty if qty > 0 else None,
                            )
                        )

            return Product(
                name=raw.get("name", "Unknown"),
                url=raw.get("url", ""),
                sku=raw.get("sku", ""),
                price=Decimal(str(raw.get("price", 0))),
                original_price=Decimal(str(raw["original_price"]))
                if raw.get("original_price")
                else None,
                category=category,
                collection=collection,
                variants=variants,
            )

        except Exception as e:
            logger.warning(f"Failed to build product: {e}")
            return None
