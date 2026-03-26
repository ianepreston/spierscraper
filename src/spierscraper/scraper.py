"""Core scraping engine for Spier & Mackay website."""

import asyncio
import logging
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

import httpx
from selectolax.parser import HTMLParser, Node
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import CategoryFilter, Config
from .filters import categorize_product
from .models import DiscoveredOptions, GarmentCategory, Product, ProductVariant

logger = logging.getLogger(__name__)

# Collections to auto-discover from navigation
CLEARANCE_KEYWORDS = ["clearance", "odds", "ends", "sale"]

# User agent rotation - fmt: off
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0",
]


@dataclass
class ProductOption:
    """An option (fit or size) with its internal IDs."""

    name: str  # e.g., "Contemporary", "33"
    option_id: str  # e.g., "883"
    option_value_id: str  # e.g., "1532"


@dataclass
class ProductOptions:
    """All options parsed from a product page."""

    product_id: str
    fits: list[ProductOption]
    sizes: list[ProductOption]


class SpierMackayScraper:
    """Scraper for Spier & Mackay clearance and odds/ends sections."""

    def __init__(
        self,
        base_url: str = "https://www.spierandmackay.com",
        rate_limit: float = 1.5,
        config: Config | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.rate_limit = rate_limit
        self.config = config
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
            params = {"page_no": page}
            # X-Requested-With header is required to get JSON response
            headers = {"X-Requested-With": "XMLHttpRequest"}

            try:
                response = await self._fetch(url, params=params, headers=headers)
                data = response.json()

                # Check if we got products (API returns HTML string in products field)
                products_html = data.get("products", "")
                if not products_html or not isinstance(products_html, str):
                    break

                # Parse the HTML to extract product data
                page_products = self._parse_products_html(products_html, collection_slug)
                if not page_products:
                    break

                products.extend(page_products)
                logger.debug(f"Page {page}: {len(page_products)} products")

                # Check for more pages - API returns next page_no or we got fewer products
                next_page = data.get("page_no")
                if not next_page or next_page <= page:
                    break

                page = next_page

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    break
                raise
            except Exception as e:
                # Fall back to HTML scraping
                logger.debug(f"API failed for {collection_slug}: {e}, trying HTML")
                return await self._fetch_collection_html(collection_slug)

        logger.info(f"Collection {collection_slug}: {len(products)} products total")
        return products

    def _parse_products_html(self, html: str, collection_slug: str) -> list[dict[str, Any]]:
        """Parse product HTML returned by the collection API."""
        tree = HTMLParser(html)
        products: list[dict[str, Any]] = []

        # Find product cards - site uses .item-product class
        for card in tree.css(".item-product"):
            product_data = self._parse_product_card(card, collection_slug)
            if product_data:
                products.append(product_data)

        return products

    async def _fetch_collection_html(self, collection_slug: str) -> list[dict[str, Any]]:
        """Fallback: scrape collection page HTML."""
        url = f"{self.base_url}/collection/{collection_slug}"
        response = await self._fetch(url)
        tree = HTMLParser(response.text)

        products: list[dict[str, Any]] = []

        # Find product cards - site uses .item-product class
        for card in tree.css(".item-product"):
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

        # Extract SKU from URL (e.g., /product/cream-birdseye-dress-shirt-11081-c7f5k)
        sku_match = re.search(r"/product/[^/]+-([a-z0-9-]+)$", str(href), re.I)
        sku = sku_match.group(1).upper() if sku_match else ""

        # Product name - site uses .prod-name
        name_el = card.css_first(".prod-name")
        name = name_el.text(strip=True) if name_el else "Unknown"

        # Price - site uses .prod-price for sale price
        price_el = card.css_first(".prod-price")
        price_text = price_el.text(strip=True) if price_el else "$0"
        price = self._parse_price(price_text)

        # Original price - site uses .prod-price1 for original/compare price
        orig_el = card.css_first(".prod-price1")
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

    async def fetch_product_options(self, product_url: str) -> ProductOptions | None:
        """Fetch product options (fit/size) with their internal IDs."""
        response = await self._fetch(product_url)
        tree = HTMLParser(response.text)

        # Get product ID
        product_id_el = tree.css_first("#filter_product_id")
        if not product_id_el:
            logger.warning(f"No product ID found for {product_url}")
            return None

        product_id = product_id_el.attributes.get("value", "")
        if not product_id:
            return None

        # Parse options from #option_product_details (not the notify section)
        option_details = tree.css_first("#option_product_details")
        if not option_details:
            logger.warning(f"No option details found for {product_url}")
            return None

        fits, sizes = self._parse_option_groups(option_details)

        logger.debug(f"Product {product_id}: {len(fits)} fits, {len(sizes)} sizes")
        return ProductOptions(product_id=product_id, fits=fits, sizes=sizes)

    def _parse_option_groups(
        self, container: Node
    ) -> tuple[list[ProductOption], list[ProductOption]]:
        """Parse fit and size option groups from the container.

        The site uses the same class (size1) for both fit and size options,
        but they have different option_id values. We identify which is which
        by looking at the section titles ("- Fit" vs "- Size").
        """
        fits: list[ProductOption] = []
        sizes: list[ProductOption] = []

        # Find all option groups (each has a title wrapper followed by options)
        fit_option_id: str | None = None
        size_option_id: str | None = None

        # First, identify which option_id corresponds to fit vs size
        for title_div in container.css(".modal-title1"):
            title_text = title_div.text(strip=True).lower()

            # Find the next collar-options div
            parent = title_div.parent
            if parent:
                grandparent = parent.parent
                if grandparent:
                    # Look for the next sibling with collar-options
                    next_sibling = grandparent.next
                    while next_sibling:
                        if hasattr(next_sibling, "css"):
                            options_div = next_sibling.css_first(".collar-options")
                            if options_div:
                                # Get the first option to find its option_id
                                first_option = options_div.css_first("[option_id]")
                                if first_option:
                                    opt_id = first_option.attributes.get("option_id", "")
                                    if "fit" in title_text:
                                        fit_option_id = opt_id
                                    elif "size" in title_text:
                                        size_option_id = opt_id
                                break
                        next_sibling = next_sibling.next if hasattr(next_sibling, "next") else None

        # Now parse all options and group by their option_id
        seen_values: set[str] = set()
        for el in container.css("[option_id][option_value_id]"):
            option_id = el.attributes.get("option_id", "")
            option_value_id = el.attributes.get("option_value_id", "")

            if not option_id or not option_value_id:
                continue

            # Skip duplicates
            if option_value_id in seen_values:
                continue
            seen_values.add(option_value_id)

            # Get the text label from span child
            span = el.css_first("span")
            name = span.text(strip=True) if span else ""

            if not name:
                continue

            opt = ProductOption(
                name=name,
                option_id=option_id,
                option_value_id=option_value_id,
            )

            if option_id == fit_option_id:
                fits.append(opt)
            elif option_id == size_option_id:
                sizes.append(opt)
            else:
                # If we couldn't determine type from titles, use heuristics
                # Sizes are typically numeric or have number patterns
                if name.isdigit() or re.match(r"^\d+[A-Z]?$", name) or "/" in name:
                    sizes.append(opt)
                else:
                    fits.append(opt)

        return fits, sizes

    async def check_stock(self, product_id: str, fit_value_id: str, size_value_id: str) -> int:
        """Check stock for a specific fit/size combination.

        Returns the quantity in stock (0 if out of stock).
        """
        url = f"{self.base_url}/Product/get_sku_qty"

        try:
            sku_option = f"{fit_value_id},{size_value_id}"
            response = await self._post(
                url,
                data={"sku_option": sku_option, "product_id": product_id},
                headers={"X-Requested-With": "XMLHttpRequest"},
            )
            data = response.json()

            if isinstance(data, dict):
                # wh_2 is the main warehouse stock
                wh_2 = data.get("wh_2", 0)
                return int(wh_2) if wh_2 else 0

        except Exception as e:
            logger.warning(f"Failed to check stock for {product_id}: {e}")

        return 0

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
                logger.info(f"Processing {len(raw_products)} products from {slug}")

                for raw in raw_products:
                    product = await self._build_product(raw, slug)
                    if product:
                        all_products.append(product)

            except Exception as e:
                logger.error(f"Failed to scrape collection {slug}: {e}")
                continue

        logger.info(f"Total products scraped: {len(all_products)}")
        return all_products

    def _get_filter_for_category(self, category: GarmentCategory) -> CategoryFilter | None:
        """Get filter config for a category, if one exists."""
        if not self.config:
            return None
        return self.config.get_filter(category.value)

    async def _build_product(self, raw: dict[str, Any], collection: str) -> Product | None:
        """Build a Product model from raw scraped data.

        Only fetches detailed stock info for products in categories we care about,
        and only checks stock for fits/sizes in our config.
        """
        try:
            name = raw.get("name", "Unknown")
            category = categorize_product(name, collection)

            # Check if we have a filter for this category
            category_filter = self._get_filter_for_category(category)

            # If no config or no filter for this category, skip fetching details
            # but still return basic product info (might be useful for debugging)
            if not category_filter:
                logger.debug(f"Skipping {name}: no filter for {category.value}")
                return Product(
                    name=name,
                    url=raw.get("url", ""),
                    sku=raw.get("sku", ""),
                    price=Decimal(str(raw.get("price", 0))),
                    original_price=Decimal(str(raw["original_price"]))
                    if raw.get("original_price")
                    else None,
                    category=category,
                    collection=collection,
                    variants=[],
                )

            # Fetch product options to get fit/size IDs
            variants: list[ProductVariant] = []
            product_url = raw.get("url", "")

            if product_url:
                options = await self.fetch_product_options(product_url)

                if options:
                    variants = await self._check_matching_variants(
                        options, category_filter, raw.get("sku", "")
                    )

            return Product(
                name=name,
                url=product_url,
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
            logger.warning(f"Failed to build product {raw.get('name', 'unknown')}: {e}")
            return None

    async def _check_matching_variants(
        self,
        options: ProductOptions,
        category_filter: CategoryFilter,
        base_sku: str,
    ) -> list[ProductVariant]:
        """Check stock only for fit/size combinations that match our filter."""
        variants: list[ProductVariant] = []

        # Find fits that match our filter (or all if no fits specified)
        matching_fits = []
        if category_filter.fits:
            for opt in options.fits:
                if any(
                    f.lower() in opt.name.lower() or opt.name.lower() in f.lower()
                    for f in category_filter.fits
                ):
                    matching_fits.append(opt)
        else:
            # No fit filter = match all (e.g., knitwear)
            matching_fits = (
                options.fits
                if options.fits
                else [ProductOption(name="Standard", option_id="", option_value_id="")]
            )

        # Find sizes that match our filter
        matching_sizes = []
        if category_filter.sizes:
            for opt in options.sizes:
                if opt.name in category_filter.sizes:
                    matching_sizes.append(opt)
        else:
            matching_sizes = options.sizes

        if not matching_sizes:
            logger.debug("No matching sizes found for product")
            return variants

        # Check stock for each matching combination
        for fit in matching_fits:
            for size in matching_sizes:
                # Handle products without fit options
                if fit.option_value_id and size.option_value_id:
                    qty = await self.check_stock(
                        options.product_id, fit.option_value_id, size.option_value_id
                    )
                else:
                    # For products with only size (no fit), check with just size
                    qty = 0  # Skip for now, would need different API call

                variant_sku = f"{base_sku}-{fit.name}-{size.name}".strip("-")
                variants.append(
                    ProductVariant(
                        fit=fit.name,
                        size=size.name,
                        sku=variant_sku,
                        in_stock=qty > 0,
                        quantity=qty if qty > 0 else None,
                    )
                )

        return variants

    async def discover_available_options(self) -> DiscoveredOptions:
        """Discover all available category/fit/size combinations from the site.

        This scrapes all clearance products and aggregates the available options
        without checking stock. Useful for understanding what the site offers
        and validating your config.yaml filters.

        Returns:
            DiscoveredOptions with all categories, fits, and sizes found.
        """
        from collections import defaultdict

        from .models import CategoryOptions

        logger.info("Discovering available options...")

        # Track unique fits and sizes per category
        category_fits: dict[str, set[str]] = defaultdict(set)
        category_sizes: dict[str, set[str]] = defaultdict(set)

        collections = await self.discover_clearance_collections()

        if not collections:
            logger.warning("No clearance collections found")
            return DiscoveredOptions()

        for slug in collections:
            try:
                raw_products = await self.fetch_collection_products(slug)
                logger.info(f"Discovering options from {len(raw_products)} products in {slug}")

                for raw in raw_products:
                    name = raw.get("name", "Unknown")
                    category = categorize_product(name, slug)
                    product_url = raw.get("url", "")

                    if not product_url:
                        continue

                    # Fetch options for this product
                    try:
                        options = await self.fetch_product_options(product_url)
                        if options:
                            for fit in options.fits:
                                category_fits[category.value].add(fit.name)
                            for size in options.sizes:
                                category_sizes[category.value].add(size.name)
                    except Exception as e:
                        logger.debug(f"Failed to fetch options for {name}: {e}")
                        continue

            except Exception as e:
                logger.error(f"Failed to process collection {slug}: {e}")
                continue

        # Build the result
        result = DiscoveredOptions()
        all_categories = set(category_fits.keys()) | set(category_sizes.keys())

        for cat_name in sorted(all_categories):
            fits = sorted(category_fits.get(cat_name, set()))
            sizes = self._sort_sizes(list(category_sizes.get(cat_name, set())))
            result.filters[cat_name] = CategoryOptions(fits=fits, sizes=sizes)

        logger.info(f"Discovered options for {len(result.filters)} categories")
        return result

    def _sort_sizes(self, sizes: list[str]) -> list[str]:
        """Sort sizes in a sensible order (numeric first, then alphanumeric)."""

        def size_key(s: str) -> tuple[int, float | str, str]:
            # Try to extract numeric part for sorting
            import re

            # Pure numeric (e.g., "33", "34")
            if s.isdigit():
                return (0, float(s), s)

            # Numeric with suffix (e.g., "40R", "40S", "40L")
            match = re.match(r"^(\d+)([A-Z]*)$", s)
            if match:
                num, suffix = match.groups()
                return (1, float(num), suffix)

            # Fraction format (e.g., "15.5/34")
            if "/" in s:
                parts = s.split("/")
                try:
                    return (2, float(parts[0]), s)
                except ValueError:
                    pass

            # Alphabetic sizes (XS, S, M, L, XL, etc.)
            size_order = {"xxs": 0, "xs": 1, "s": 2, "m": 3, "l": 4, "xl": 5, "xxl": 6}
            lower = s.lower()
            if lower in size_order:
                return (3, size_order[lower], s)

            # Fallback: alphabetic
            return (4, 0, s)

        return sorted(sizes, key=size_key)
