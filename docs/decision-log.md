# Decision Log

Tracking decisions made during implementation where ambiguity existed.

---

## Phase 1: Scaffolding

### Python Version
**Decision:** Python 3.12
**Rationale:** Latest stable with good Nix support, modern typing features

### Async Runtime
**Decision:** Use `asyncio` with `httpx` (no `trio` or `anyio`)
**Rationale:** Simpler, httpx native support, sufficient for sequential scraping with rate limits

### HTML Parser
**Decision:** `selectolax` over `beautifulsoup4`
**Rationale:** 10-30x faster, sufficient CSS selector support for this use case

### pydantic-settings Removed
**Decision:** Use plain `pydantic.BaseModel` instead of `pydantic-settings`
**Rationale:** Manual env var loading is simpler; pydantic-settings had validation issues with mixed sources

---

## Phase 2: Scraping Engine

### Collection Discovery Validation
**Finding:** Live test confirmed 10 clearance/sale collections discovered:
- `clearance-rack`, `clearance-suits`, `clearance-jackets`
- `odds--ends-chinos`, `odds--ends-trousers-from-4999!`, `odds--ends-knitwear`, etc.
- `sale-shirts`, `all-sale-2024`

### API vs HTML Approach
**Decision:** Hybrid approach implemented as planned
- Collection discovery: HTML parsing of navigation menu
- Product listing: API endpoint with HTML fallback
- Product details: HTML parsing of product pages
- Stock levels: API endpoint

### SKU Structure Observation
**Finding:** Product URLs contain SKU patterns like `/product/brown---chino---ry-3038-chn-01-ss22`
- The trailing segment appears to be the SKU
- Stock API expects SKU variations with fit/size suffixes

---
