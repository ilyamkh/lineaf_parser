# Phase 2: Scrapers - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Playwright spiders for all three competitor sites (askona.ru, ormatek.ru, sonum.ru). Collect mattresses 160×200 with all available fields, store in the database from Phase 1, detect new and removed products. This phase delivers a working scraper pipeline that fills the database with real data.

</domain>

<decisions>
## Implementation Decisions

### Обработка пропусков (Missing Fields)
- When a field is not found on a site, try to find an analogous field (naming may vary across sites)
- If field truly doesn't exist → store NULL, save the product anyway
- Minimum required fields: name + at least one price — products without these are skipped
- No logging of missing optional fields — NULLs are visible in the dashboard
- Use Excel file (askona_160x200_full2705.xlsx) as reference for expected field names and mapping

### Стратегия парсинга (Scraping Strategy)
- Run spiders sequentially: one site at a time (easier to debug, less load)
- Two-stage: catalog page → individual product page (collect links from catalog, then visit each product)
- Random delays 2-5 seconds between page requests for anti-bot masking
- Claude's Discretion: User-Agent and header configuration based on site anti-bot behavior

### Обнаружение изменений (Change Detection)
- New product: first appearance of URL in database (source_site + source_url not in products table)
- Removed product: one missed scrape → set is_active=false immediately
- Price change tracking: NOT in scraper scope — just save snapshots, comparison happens in dashboard (Phase 3)
- If 0 products scraped from a site → record as failed in scrape_runs, do NOT set existing products as inactive

### Обработка ошибок (Error Handling)
- Bot block (CAPTCHA, 403): retry after 30-60 second pause, 2-3 attempts
- Zero results: log detailed error description with all errors for debugging
- Claude's Discretion: page load timeout (based on site performance)
- All errors must be logged with enough detail to debug issues

### Claude's Discretion
- User-Agent / header configuration
- Page load timeout per site
- Specific CSS/XPath selectors (determined by site structure research)
- Whether to use Camoufox or plain Playwright (based on anti-bot detection)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Product` model (src/lineaf/models/product.py): UniqueConstraint on (source_site, source_url) — enables UPSERT
- `PriceSnapshot` model: NUMERIC(12,2) prices, FK to products and scrape_runs
- `ScrapeRun` model: status, started_at, finished_at, items_scraped, error_message
- `database.py`: SessionLocal, get_db() — ready for use in scraper pipeline
- `askona_160x200_full2705.xlsx`: reference for field name mapping

### Established Patterns
- SQLAlchemy 2.0 Mapped[] + mapped_column() style
- uv for dependency management
- pydantic-settings for configuration

### Integration Points
- Scrapers INSERT into products (UPSERT via source_site+source_url), price_snapshots, scrape_runs
- is_active flag on products: set False when product disappears from catalog
- All nullable attribute columns: firmness, height_cm, filler, cover_material, weight_kg

</code_context>

<specifics>
## Specific Ideas

- User previously collected Askona data manually — Excel shows expected field structure
- Fields may be named differently across sites — need flexible mapping per spider
- User wants detailed error logging with descriptions when parsing fails, to facilitate debugging
- Sequential execution preferred for easier debugging during development

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-scrapers*
*Context gathered: 2026-03-14*
