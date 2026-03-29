# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important: Always Run Checks

**Before telling the user that a feature works or that code changes are complete, always run `make check` to verify that linting, type checking, and tests all pass.** Do not claim code is working without running the full check suite first.

## Build & Development Commands

```bash
# Enter nix dev shell (provides Python 3.12 + all deps)
nix develop

# Run tests
make test                    # or: pytest tests/ -v
pytest tests/test_scraper.py -v  # single test file
pytest tests/test_scraper.py::test_name -v  # single test

# Linting and type checking
make lint                    # ruff check + format check
make lint-fix                # auto-fix lint issues
make type-check              # mypy src/
make check                   # all: lint + type-check + test

# Run scraper
python -m spierscraper --dry-run --verbose  # test without sending notifications
DISCORD_WEBHOOK_URL="..." python -m spierscraper  # real run

# Build Docker image
make docker                  # nix build .#docker && docker load
make docker-release          # build + tag with CalVer (YYYY.MM.DD.N)
make docker-release REGISTRY=ghcr.io/user  # also push to registry
```

## Architecture

### Data Flow
1. **Scraper** (`scraper.py`) discovers clearance/sale collections from site navigation
2. Products fetched via AJAX API (`/Category/collection_view/{slug}`) with HTML fallback
3. **Filters** (`filters.py`) categorize products and match against user config
4. **Cache** (`cache.py`) tracks seen items to avoid duplicate notifications (in-memory or diskcache)
5. **Notifier** (`notifier.py`) sends Discord embeds for new matches

### Key Models (`models.py`)
- `GarmentCategory` enum: pants, chinos, sport_coats, suits, shirts, knitwear, outerwear, other
- `Product`: scraped item with price, variants, collection
- `ProductVariant`: fit/size/sku/stock for a specific combination
- `ProductMatch`: product + matching variants after filtering

### Configuration (`config.py`)
- YAML file defines filters by category (fits + sizes)
- `DISCORD_WEBHOOK_URL` env var for secrets
- Categories not in config are ignored (opt-in filtering)

### Scraping Strategy
- Hybrid: AJAX API for listings, HTML parsing for product details
- Rate-limited with configurable delay (default 1.5s)
- User-agent rotation
- Retry with exponential backoff via tenacity

### Site API Details
- **Collection listing**: `GET /Category/collection_view/{slug}?page_no=N` with `X-Requested-With: XMLHttpRequest`
- **Stock check**: `POST /Product/get_sku_qty` with `sku_option=fit_value_id,size_value_id&product_id=...`
  - Response: `{"wh_2": quantity, "product_code": "..."}` - `wh_2 > 0` means in stock
- Product pages have options in `#option_product_details` with `option_id` and `option_value_id` attributes
- Fits and sizes both use `size1` class but have different `option_id` values; distinguished by section title

### Performance Optimization
- Only fetches product details for categories with configured filters
- Only checks stock for fit/size combinations matching the user's config
- This reduces API calls from O(products × fits × sizes) to O(filtered_products × matching_combinations)

## Testing

Tests use `respx` to mock HTTP requests. Key fixtures in `conftest.py`:
- `sample_config`: pre-built Config with pants/chinos filters
- `sample_products_html`, `sample_api_response`: mock HTML matching real site structure
- Uses `pytest-asyncio` with `asyncio_mode = "auto"`

## Tech Stack
- Python 3.12, async with httpx
- selectolax for HTML parsing (faster than BeautifulSoup)
- pydantic for models/config validation
- diskcache for persistent change detection
- Nix flakes for reproducible dev env and Docker builds
