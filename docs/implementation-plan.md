# Spier & Mackay Scraper - Implementation Plan

## Executive Summary

This plan outlines building a web scraper for Spier & Mackay's
clearance/odds-and-ends sections to find in-stock items matching user-specified
size and fit criteria, with Discord webhook notifications.

---

## Site Analysis Findings

From reconnaissance of the target site:

1. **Architecture**: Dynamic AJAX-loaded content with infinite scroll pagination
2. **Key API Endpoints Discovered**:
   - `Category/collection_view/{slug}` - Fetches product listings for a
     collection
   - `Product/get_sku_qty` - Retrieves stock quantities for specific SKUs
   - `Product/hideshowfilter` - Product option filtering
3. **Product Variation Patterns**:
   - **Pants/Chinos**: Fit (Extra Slim, Slim, Contemporary) + Waist Size (28-40)
   - **Sport Coats**: Cut (Moro, Neo, Relaxed, etc.) + Chest Size
   - **Shirts**: Fit + Collar/Sleeve sizing
4. **Collections to Target**:
   - `/collection/clearance-rack`
   - `/collection/all-clearance`
   - Various odds-and-ends subcategories

---

## Implementation Phases

### Phase 1: Project Scaffolding & Dev Environment

**Deliverables:**

- Nix flake with dev shell and container build
- Basic Python project structure with pyproject.toml
- Pre-commit hooks (ruff, mypy)
- Makefile for common tasks

**Structure:**

```
spierscraper/
├── flake.nix
├── flake.lock
├── pyproject.toml
├── Makefile
├── config.example.yaml
├── src/
│   └── spierscraper/
│       ├── __init__.py
│       ├── __main__.py
│       ├── config.py
│       ├── scraper.py
│       ├── models.py
│       ├── filters.py
│       ├── notifier.py
│       └── cache.py
├── tests/
│   ├── fixtures/
│   ├── test_scraper.py
│   ├── test_filters.py
│   └── test_notifier.py
└── docs/
```

---

### Phase 2: Core Scraping Engine

**Deliverables:**

- HTTP client with rate limiting and retry logic
- Collection page parser (handle infinite scroll pagination)
- Product detail fetcher
- Stock/SKU resolver

**Key Components:**

```python
# Pseudocode structure
class SpierMackayScraper:
    async def fetch_collection(collection_slug: str) -> list[ProductListing]
    async def fetch_product_details(product_url: str) -> ProductDetails
    async def fetch_stock_levels(sku: str) -> dict[str, int]
```

**Rate Limiting Strategy:**

- 1-2 second delay between requests
- Exponential backoff on 429/5xx responses
- Respect robots.txt
- Rotate user-agent strings

---

### Phase 3: Data Models & Filtering

**Deliverables:**

- Pydantic models for products, variants, stock
- Filter engine supporting arbitrary fit/size combinations
- Config file parser

**Models:**

```python
class ProductVariant(BaseModel):
    fit: str           # "Slim", "Contemporary", "Extra Slim", etc.
    size: str          # "33", "40R", "15.5/34", etc.
    sku: str
    in_stock: bool
    quantity: int | None

class Product(BaseModel):
    name: str
    url: str
    price: Decimal
    original_price: Decimal | None
    category: str      # "pants", "sport_coat", "shirt", etc.
    variants: list[ProductVariant]
```

**Config Format (YAML):**

**odds and ends should be dynamically identified, not part of config** **Discord
webhook URL is sensitive have an option to pass it as an environment var**

```yaml
# config.yaml
collections:
  - clearance-rack
  - odds--ends-trousers-from-4999!
  - odds--ends-chinos-from-2499

filters:
  pants:
    fits: ["Contemporary", "Slim"]
    sizes: ["33", "34"]
  chinos:
    fits: ["Contemporary"]
    sizes: ["33"]
  sport_coats:
    fits: ["Moro Cut (Regular)"]
    sizes: ["40R", "40S"]

discord_webhook_url: "https://discord.com/api/webhooks/..."

# Optional settings
rate_limit_seconds: 1.5
```

---

### Phase 4: Discord Notification System

**Deliverables:**

- Discord webhook client
- Message formatter with embeds
- Batched notifications (avoid spam)

**Message Format:**

```
🎯 3 New Matches Found!

**Brown Chino - RY-3038**
$24.99 (was $68.00) - 63% off
✓ Contemporary 33 (2 in stock)
🔗 [View Product](url)

**Navy Trousers - ABC-123**
...
```

---

### Phase 5: Change Detection (Stretch Goal)

**Deliverables:**

- In-memory cache with TTL
- Diff engine to compare runs
- "New items only" mode

**Approach:**

- Store SHA256 hash of `{sku}:{in_stock}:{quantity}` per product
- On each run, compare against cache
- Report only: new products, restocks, price drops

---

### Phase 6: Container & CI/CD

**Deliverables:**

- Multi-stage Dockerfile via Nix
- GitHub Actions workflow for build/push
- Health check endpoint (optional)

---

## Ambiguities & Recommendations

### 1. API vs HTML Scraping Strategy

**Ambiguity:** The site has both API endpoints and rendered HTML. Which
approach?

**Recommendation:** **Hybrid approach**

- Use API endpoints (`Category/collection_view`, `Product/get_sku_qty`) where
  they exist and are stable
- Fall back to HTML parsing for data not in API responses
- Benefit: APIs are faster and more reliable; HTML as fallback

**Alternative:** Pure HTML scraping (more resilient to API changes but slower)

**Decision needed:** Prefer API-first or HTML-first? - Agree with recommendation

---

### 2. Product Category Normalization

**Ambiguity:** Fits and sizes vary significantly by product type:

- Pants: "Contemporary 33"
- Sport coats: "Moro Cut 40R"
- Shirts: "Slim 15.5/34"

**Recommendation:** Category-aware filtering with explicit mappings in config.
User specifies filters per category (as shown in config example above).

**Alternative:** Generic "fit" and "size" fields with exact string matching

**Decision needed:** Is category-aware filtering acceptable, or do you want a
simpler unified model? - Category aware is preferred. If sizes are not specified
for a category assume the user is not interested in that category.

---

### 3. Collection Discovery

**Ambiguity:** Should the scraper auto-discover all clearance/odds-ends
collections, or use an explicit list?

**Recommendation:** **Explicit list in config**

- More predictable behavior
- User controls scope
- Easier to debug

**Alternative:** Auto-discovery by scraping the navigation menu

**Decision needed:** Explicit collection list or auto-discovery? - Auto
discovery

---

### 4. Scheduling & Execution Model

**Ambiguity:** How should the scraper run?

- One-shot CLI invocation
- Long-running daemon with internal scheduler
- External cron/k8s CronJob

**Recommendation:** **One-shot CLI** triggered by external scheduler (k8s
CronJob)

- Simpler architecture
- Crash recovery handled by k8s
- Easier testing
- Memory cache can use k8s ConfigMap/file for persistence between runs

**Alternative:** Built-in scheduler with configurable interval

**Decision needed:** One-shot CLI or daemon with scheduler? One-shot

---

### 5. Notification Deduplication Window

**Ambiguity:** How long should an item be "seen" before re-notifying?

**Recommendation:** **Configurable TTL** (default 24 hours)

- If cache persists (file-backed), don't re-notify for items seen within TTL
- If cache is lost (crash/restart), one-time re-notification is acceptable

**Decision needed:** Is 24-hour default acceptable? Should cache be file-backed
or pure in-memory? 24 hour is acceptable. File or config-map is nice but pure
memory is fine. Fallback to pure memory if other option isn't provided

---

### 6. Error Handling & Alerting

**Ambiguity:** What happens when scraping fails?

**Recommendation:**

- Log errors to stderr
- Send Discord notification on complete failure (optional)
- Exit with non-zero code for k8s to detect

**Decision needed:** Should scraper failures also notify Discord, or just log?
Notify discord.

---

## Implementation Order

| Phase               | Effort | Dependencies |
| ------------------- | ------ | ------------ |
| 1. Scaffolding      | Small  | None         |
| 2. Scraper Core     | Medium | Phase 1      |
| 3. Models & Filters | Small  | Phase 2      |
| 4. Discord Notifier | Small  | Phase 3      |
| 5. Change Detection | Small  | Phase 4      |
| 6. Container/CI     | Small  | Phase 5      |

Recommended approach: Complete phases 1-4 for MVP, then iterate.

---

## Testing Strategy

1. **Unit Tests**: Filter logic, config parsing, message formatting
2. **Integration Tests**: Mock HTTP responses (fixtures captured from real site)
3. **Live Tests**: Optional flag to hit real site (for manual validation)

Fixture capture approach:

- Run against live site once
- Save raw responses to `tests/fixtures/`
- Mock httpx client in tests to return fixtures

---

## Technical Stack Recommendation

| Component   | Choice                           | Rationale                                 |
| ----------- | -------------------------------- | ----------------------------------------- |
| HTTP Client | `httpx`                          | Async, modern, good timeout/retry support |
| HTML Parser | `selectolax` or `beautifulsoup4` | Fast DOM traversal                        |
| Config      | `pydantic-settings` + YAML       | Type-safe, validation built-in            |
| Discord     | Raw `httpx` POST                 | Simple webhook, no SDK needed             |
| Caching     | `diskcache` or dict+pickle       | Simple, file-backed optional              |
| Testing     | `pytest` + `pytest-asyncio`      | Standard                                  |

---

## Questions for Your Review

1. **API vs HTML scraping** - API-first (faster, less stable) or HTML-first
   (slower, more resilient)? API with html fallback
2. **Category-aware filters** - Acceptable to have separate filter configs per
   garment type? preferred to have per garment.
3. **Collection list** - Explicit in config, or auto-discover from navigation?
   auto discover ideal
4. **Execution model** - One-shot CLI (recommended) or daemon? one shot
5. **Cache persistence** - File-backed between runs, or in-memory only? file
   backed if provided, fallback to in memory
6. **Failure notifications** - Send Discord alert on scraper failure? yes.

Once you confirm these decisions, I can begin implementation starting with
Phase 1.
