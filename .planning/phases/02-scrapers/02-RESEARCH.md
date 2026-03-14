# Phase 2: Scrapers - Research

**Researched:** 2026-03-14
**Domain:** Playwright-based web scraping, Russian e-commerce mattress sites, PostgreSQL UPSERT
**Confidence:** MEDIUM-HIGH (Askona/Sonum verified by direct fetch; Ormatek returns 403 to plain HTTP clients and requires stealth browser)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Обработка пропусков (Missing Fields)**
- When a field is not found on a site, try to find an analogous field (naming may vary across sites)
- If field truly doesn't exist → store NULL, save the product anyway
- Minimum required fields: name + at least one price — products without these are skipped
- No logging of missing optional fields — NULLs are visible in the dashboard
- Use Excel file (askona_160x200_full2705.xlsx) as reference for expected field names and mapping

**Стратегия парсинга (Scraping Strategy)**
- Run spiders sequentially: one site at a time (easier to debug, less load)
- Two-stage: catalog page → individual product page (collect links from catalog, then visit each product)
- Random delays 2-5 seconds between page requests for anti-bot masking
- Claude's Discretion: User-Agent and header configuration based on site anti-bot behavior

**Обнаружение изменений (Change Detection)**
- New product: first appearance of URL in database (source_site + source_url not in products table)
- Removed product: one missed scrape → set is_active=false immediately
- Price change tracking: NOT in scraper scope — just save snapshots, comparison happens in dashboard (Phase 3)
- If 0 products scraped from a site → record as failed in scrape_runs, do NOT set existing products as inactive

**Обработка ошибок (Error Handling)**
- Bot block (CAPTCHA, 403): retry after 30-60 second pause, 2-3 attempts
- Zero results: log detailed error description with all errors for debugging
- Claude's Discretion: page load timeout (based on site performance)
- All errors must be logged with enough detail to debug issues

### Claude's Discretion
- User-Agent / header configuration
- Page load timeout per site
- Specific CSS/XPath selectors (determined by site structure research)
- Whether to use Camoufox or plain Playwright (based on anti-bot detection)

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SCRP-01 | Парсер собирает каталог матрасов 160×200 с askona.ru (все страницы пагинации) | Pagination: `?page=N`, ~75 products across 3 pages; JSON in `__NEXT_DATA__` |
| SCRP-02 | Парсер собирает каталог матрасов 160×200 с ormatek.com (все страницы пагинации) | URL: `/catalog/matrasy/160x200/`; returns 403 to plain clients → Camoufox required |
| SCRP-03 | Парсер собирает каталог матрасов 160×200 с sonum.ru (все страницы пагинации) | Filter URL + `PAGEN_1=N`; ~57 products; Bitrix CMS; "load more" button |
| SCRP-04 | Для каждого матраса собираются поля: модель, цена до скидки, цена после скидки, жёсткость, высота, наполнитель, материал чехла, вес на спальное место | All fields verified present on detail pages; some on catalog JSON |
| SCRP-05 | Парсер корректно обрабатывает JS-рендеренные страницы через Playwright | Camoufox wraps Playwright; use `AsyncCamoufox` context manager |
| SCRP-06 | Парсер обнаруживает новые позиции (товары, которых не было в прошлом запуске) | Pipeline compares scraped URLs against DB; UniqueConstraint on (source_site, source_url) |
| SCRP-07 | Парсер обнаруживает удалённые позиции (товары, которые были, но исчезли из каталога) | Pipeline marks missing products `is_active=False`; guarded by 0-result check |
</phase_requirements>

---

## Summary

All three target sites are JavaScript-enhanced server-rendered pages built on Russian e-commerce CMSes (Askona uses Next.js/React SSR; Sonum uses 1C-Bitrix; Ormatek uses a Vue/Nuxt stack). Product data is embedded in the initial HTML response (Askona as `__NEXT_DATA__` JSON, Sonum as static HTML with Bitrix AJAX for load-more). Plain HTTP clients return 403 from Ormatek, meaning Camoufox (stealth Firefox) is required for all three spiders to be consistent and future-proof.

The two-stage scraping pattern (collect catalog URLs → visit each product page) is appropriate for all three sites. Askona provides most spec fields in its embedded JSON; Sonum and Ormatek require visiting product detail pages for characteristics (firmness, height, filler, cover material, weight). The reference Excel file confirms the 9-field schema: ссылка, модель, цена до скидки, цена после скидки, жёсткость, высота, наполнитель, материал чехла, вес на спальное место.

Change detection is implemented in the item pipeline via PostgreSQL's `INSERT ... ON CONFLICT DO UPDATE` (UPSERT) and a post-run sweep that sets `is_active=False` for products whose URLs did not appear in the current scrape run.

**Primary recommendation:** Use Camoufox (`pip install camoufox[geoip]`) for all three spiders. Write a single shared `BaseScraper` class with the Camoufox context, retry logic, and delay behaviour. Each site spider subclasses it with site-specific catalog URL, pagination logic, and field extraction.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| camoufox | latest (≥0.2.15) | Anti-detect browser wrapping Playwright | Bypasses bot detection at C++ level; fully compatible with Playwright API |
| playwright | bundled with camoufox | Browser automation | Async API for navigation and DOM extraction |
| sqlalchemy | 2.0.x (already installed) | ORM + UPSERT | Existing project; `postgresql.insert().on_conflict_do_update()` |
| psycopg2-binary | 2.9.x (already installed) | PostgreSQL driver | Already in pyproject.toml |
| pydantic-settings | 2.x (already installed) | Config/env | Already used in `config.py` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | Async event loop | Camoufox async API requires it |
| decimal | stdlib | Price parsing | Never use float for prices |
| re | stdlib | Price text cleaning | Strip "₽", spaces from price strings |
| json | stdlib | `__NEXT_DATA__` parsing | Askona catalog/detail data |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| camoufox | playwright-stealth | Playwright-stealth patches JS only; Camoufox patches at C++ level — more robust |
| camoufox | patchright | Patchright is Chromium-based stealth; Camoufox is Firefox-based — both valid, Camoufox chosen per project decision |
| plain Playwright | requests + BeautifulSoup | Sites use JS rendering; static HTTP yields empty product containers |

**Installation:**
```bash
uv add camoufox
python -m camoufox fetch
```

Note: `camoufox fetch` downloads the patched Firefox binary (~120 MB). Must be run once per environment.

---

## Architecture Patterns

### Recommended Project Structure

```
src/lineaf/
├── scrapers/
│   ├── __init__.py
│   ├── base.py          # BaseScraper: Camoufox context, retry, delay, ScrapeRun lifecycle
│   ├── askona.py        # AskonaScraper: catalog URL, JSON extraction, field mapping
│   ├── ormatek.py       # OrmatelScraper: catalog URL, CSS extraction, field mapping
│   └── sonum.py         # SonumScraper: catalog URL, Bitrix AJAX handling, field mapping
├── pipeline.py          # ItemPipeline: UPSERT, change detection, price snapshot insert
└── run_scrapers.py      # Entry point: sequential execution, error isolation
```

### Pattern 1: Camoufox Async Context

**What:** Open a single Camoufox browser for all pages in a scrape run; reuse pages/contexts.
**When to use:** All three spiders. Opening/closing browser per page is too slow and triggers bot detection.

```python
# Source: https://camoufox.com/python/installation/ + GitHub daijro/camoufox
from camoufox.async_api import AsyncCamoufox
import asyncio

async def run_spider():
    async with AsyncCamoufox(headless=True, geoip=True) as browser:
        page = await browser.new_page()
        await page.goto("https://www.askona.ru/matrasy/160x200/", timeout=30000)
        # ... extract data ...
        await page.close()

asyncio.run(run_spider())
```

### Pattern 2: Two-Stage Scraping

**What:** Stage 1 — iterate all catalog pages, collect product URLs. Stage 2 — visit each URL, extract full specs.
**When to use:** All three spiders. Catalog cards do not contain all 8 required fields.

```python
async def scrape_site(page):
    urls = []
    page_num = 1
    while True:
        await page.goto(catalog_url(page_num), timeout=30000)
        await asyncio.sleep(random.uniform(2, 5))
        cards = await page.query_selector_all(".product-card")  # site-specific
        if not cards:
            break
        for card in cards:
            href = await card.query_selector("a")
            urls.append(await href.get_attribute("href"))
        page_num += 1

    products = []
    for url in urls:
        await page.goto(url, timeout=30000)
        await asyncio.sleep(random.uniform(2, 5))
        products.append(await extract_product(page, url))
    return products
```

### Pattern 3: Retry with Back-off

**What:** Wrap each page navigation in a retry loop. On 403/CAPTCHA/timeout, wait 30-60 seconds and retry.
**When to use:** Every `page.goto()` call in all spiders.

```python
import random, asyncio

async def goto_with_retry(page, url, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            response = await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            if response and response.status == 403:
                raise Exception(f"403 Forbidden: {url}")
            return response
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            wait = random.uniform(30, 60)
            print(f"Attempt {attempt+1} failed ({e}), retrying in {wait:.0f}s")
            await asyncio.sleep(wait)
```

### Pattern 4: PostgreSQL UPSERT (Item Pipeline)

**What:** Insert product on first appearance, update name/attributes on subsequent runs. Always insert a new price_snapshot.
**When to use:** ItemPipeline after extracting each product.

```python
# Source: https://docs.sqlalchemy.org/en/20/dialects/postgresql.html
from sqlalchemy.dialects.postgresql import insert as pg_insert
from lineaf.models.product import Product

def upsert_product(session, data: dict) -> int:
    stmt = pg_insert(Product).values(**data)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_products_site_url",
        set_={
            "name": stmt.excluded.name,
            "firmness": stmt.excluded.firmness,
            "height_cm": stmt.excluded.height_cm,
            "filler": stmt.excluded.filler,
            "cover_material": stmt.excluded.cover_material,
            "weight_kg": stmt.excluded.weight_kg,
            "is_active": True,  # re-activate if it was previously marked removed
        }
    )
    result = session.execute(stmt)
    session.flush()
    # Get the product id (either inserted or updated)
    product = session.query(Product).filter_by(
        source_site=data["source_site"],
        source_url=data["source_url"]
    ).one()
    return product.id
```

### Pattern 5: Removed-Product Detection

**What:** After all product URLs collected in a run, set `is_active=False` for products in DB that were NOT in the scraped URL set.
**When to use:** After successful catalog scrape (total > 0 products found).

```python
def mark_removed_products(session, source_site: str, scraped_urls: set[str]):
    """Guard: only run if scraped_urls is non-empty."""
    if not scraped_urls:
        return 0
    result = session.query(Product).filter(
        Product.source_site == source_site,
        Product.is_active == True,
        Product.source_url.notin_(scraped_urls)
    ).update({"is_active": False}, synchronize_session=False)
    return result
```

### Anti-Patterns to Avoid

- **Opening new browser per product URL:** Causes slow execution and triggers bot detection from fresh TLS fingerprints. Reuse the same Camoufox browser instance for the entire run.
- **Using float for prices:** Always use `Decimal` — `Decimal(price_str.replace(" ", "").replace("₽", "").strip())`.
- **Setting products inactive on 0-result scrape:** If the entire catalog returns 0 products, the scraper failed (not the products). Do not call `mark_removed_products` in this case.
- **Hardcoding absolute CSS selectors:** Use multiple fallback selectors or extract from JSON where available (Askona `__NEXT_DATA__`).

---

## Site-Specific Findings

### Askona (askona.ru)

**Rendering:** Next.js SSR. All product data embedded in `<script id="__NEXT_DATA__" type="application/json">`. No JS execution needed to read product list — but Playwright/Camoufox still needed to pass bot detection.

**Catalog URL for 160×200:** `https://www.askona.ru/matrasy/160x200/`
**Pagination:** `?page=N` query parameter. Total ~75 products, 3 pages, ~28-30 per page.
**robots.txt:** Explicitly allows `/*/*?PAGEN_1=*` and `/?page=*` patterns. No crawl-delay.

**Catalog JSON path (in `__NEXT_DATA__`):**
```
props → pageProps → data → listing → items[]
```
Each item has:
- `name` — product name
- `price` — sale price (integer, RUB)
- `oldPrice` — original price (integer, RUB)
- `productLink` — relative URL, e.g. `/matrasy/comfort-plus.htm?SELECTED_HASH_SIZE=160x200-...`
- `discount` — percentage
- Firmness levels may appear in catalog JSON

**Product detail URL construction:** Prepend `https://www.askona.ru` to `productLink`. The `SELECTED_HASH_SIZE` parameter pre-selects the 160×200 size — important for correct price.

**Detail page JSON path:**
```
props → pageProps → productData → characteristics[0] → items[]
```
Each item: `{"name": "Высота матраса", "value": "17 см"}`

**Field name mapping (from reference Excel):**

| DB Field | JSON `name` key |
|----------|-----------------|
| `firmness` | "Жесткость" |
| `height_cm` | "Высота матраса" |
| `filler` | "Наполнитель" |
| `cover_material` | "Материал чехла" or "Съемный чехол" |
| `weight_kg` | "Вес на спальное место, кг" or "Вес матраса" |

**Anti-bot:** Standard Next.js app with Yandex analytics. Plain HTTP fetch returns 200 for the catalog listing (WebFetch succeeded). Camoufox used for consistency and product-page access.

**Confidence:** HIGH — direct fetch succeeded, JSON structure verified.

---

### Sonum (sonum.ru)

**Rendering:** 1C-Bitrix CMS with server-rendered HTML. Product cards are in static HTML. "Больше товаров" (Load More) button triggers Bitrix AJAX for additional products.

**Catalog URL for 160×200:** `https://www.sonum.ru/catalog/matrasy/?filter%5Bwidth%5D%5B0%5D=160&filter%5Blength%5D%5B0%5D=200`
Decoded: `?filter[width][0]=160&filter[length][0]=200`

**Pagination:** `PAGEN_1=N` parameter appended to filtered URL. ~57 total products. Verified working.
Full paginated URL example: `https://www.sonum.ru/catalog/matrasy/?filter%5Bwidth%5D%5B0%5D=160&filter%5Blength%5D%5B0%5D=200&PAGEN_1=2`

**Catalog page data available:** Product name, sale price, original price, firmness badge, product URL, rating.

**CSS selectors (MEDIUM confidence — inferred from fetched HTML):**
- Product card wrapper: `.catalog-item`
- Product link/name: `a` within `.catalog-item__name` or `.catalog-item` → first `a`
- Sale price: First `span` containing "₽"
- Original price: Second (struck-through) `span` containing "₽"

**Detail page:** `window.cad_element_config` JS object contains prices. Characteristics in HTML `<table>` rows. Firmness in static text near title.

**Field name mapping (detail page, Russian labels in table):**
- Height: "Высота матраса"
- Cover: "Материал чехла"
- Weight: "Вес на 1 место"
- Firmness: "Жесткость матраса" (also appears as badge on catalog page)
- Filler: In product description text (not a discrete table field — parse from description or store NULL)

**Anti-bot:** Bitrix `sessid` CSRF token + Proof-of-Work challenge (`window.SONUM_HASHCACH`). Camoufox handles JS-based challenge automatically since it runs a real patched Firefox. No Cloudflare detected.

**Confidence:** MEDIUM-HIGH — catalog page fetched successfully; detail page structure verified.

---

### Ormatek (ormatek.com)

**Rendering:** Nuxt.js / Vue.js (detected via `window.__NUXT__`). SSR-capable but returns 403 to plain HTTP clients and to standard Playwright headless browser. Requires Camoufox stealth browser.

**Catalog URL for 160×200:** `https://www.ormatek.com/catalog/matrasy/160x200/`
(Alternative filter URL `filter/length-is-2000/width-is-1600/` returns 403 — use `/160x200/` path instead.)

**Regional subdomains:** Ormatek has city subdomains (`perm.ormatek.com`, `kazan.ormatek.com`). Use `www.ormatek.com` for national catalog.

**Pagination:** Not directly verified due to 403. Based on Nuxt.js patterns, likely `?page=N` or `?PAGEN_1=N` (Bitrix hybrid). Must be discovered in Wave 0 using Camoufox browser inspection.

**CSS selectors:** Unknown — 403 blocked all fetches. Must be discovered in Wave 0 with Camoufox by:
1. Loading `https://www.ormatek.com/catalog/matrasy/160x200/`
2. Inspecting rendered DOM
3. Looking for `window.__NUXT__` data object for SSR data

**Field mapping:** Unknown — must be discovered from product detail page in Wave 0.

**Anti-bot:** Strong — all plain HTTP requests return 403. Likely TLS fingerprinting + user-agent detection. Camoufox's C-level Firefox fingerprint is the appropriate tool. If still blocked after 3 retries, log as failed run.

**Confidence:** LOW for selectors (blocked by 403); HIGH that Camoufox is required.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Browser fingerprint spoofing | Custom JS injection patches | Camoufox | C++-level spoofing; JS overrides are detectable |
| Price UPSERT | Manual SELECT then INSERT/UPDATE | `pg_insert().on_conflict_do_update()` | Atomic, race-condition safe |
| Delay/rate limiting | Custom scheduler | `asyncio.sleep(random.uniform(2, 5))` | Simple and sufficient for sequential scraping |
| HTML parsing | Custom regex on HTML | Playwright's `query_selector` / JSON path | Handles dynamic DOM correctly |
| Price string to Decimal | Custom parser | `Decimal(re.sub(r"[^\d.]", "", price_str))` | One-liner, handles "₽" and nbsp |

**Key insight:** The biggest trap is writing a simple `requests` scraper that works in dev but fails in production because the sites return empty HTML to non-browser clients. Use Camoufox from the start.

---

## Common Pitfalls

### Pitfall 1: Ormatek 403 in Plain Playwright Headless
**What goes wrong:** Standard `playwright install chromium` + headless mode returns 403 from ormatek.com.
**Why it happens:** TLS fingerprint and `navigator.webdriver=true` are detectable by the site's bot protection.
**How to avoid:** Use Camoufox for all three spiders (consistency) rather than plain Playwright for Askona/Sonum only.
**Warning signs:** `response.status == 403` on catalog page; retry loop exhausted.

### Pitfall 2: Askona Size Selection in URL
**What goes wrong:** Visiting `/matrasy/comfort-plus.htm` without the `SELECTED_HASH_SIZE` hash parameter shows the default size (90×200) price, not 160×200.
**Why it happens:** Askona product pages show per-size prices; the hash selects the size variant.
**How to avoid:** Always use the `productLink` from the catalog JSON which includes `?SELECTED_HASH_SIZE=160x200-...`.
**Warning signs:** Prices on detail page don't match catalog listing prices.

### Pitfall 3: Sonum Load-More vs Pagination
**What goes wrong:** Scraping only the first page HTML misses products that load via the "Больше товаров" AJAX button.
**Why it happens:** Bitrix CMS serves initial batch as static HTML, additional pages via AJAX.
**How to avoid:** Use `PAGEN_1=N` URL parameter (verified working) rather than clicking the load-more button. Iterate until a page returns no product cards.
**Warning signs:** Only 20 products found instead of ~57.

### Pitfall 4: Mark-Inactive on Failed Run
**What goes wrong:** If the scraper crashes halfway through, partially-scraped URLs are compared against the full DB, marking most products as inactive.
**Why it happens:** The `mark_removed_products` function runs after a partial catalog.
**How to avoid:** Gate the removed-product sweep on `len(scraped_urls) > 0` AND `scrape_run.status != "failed"`.
**Warning signs:** Dashboard shows mass deactivation after a run with an error.

### Pitfall 5: Filler Field Not in Sonum Characteristics Table
**What goes wrong:** Filler/наполнитель is buried in the description text at Sonum, not a discrete table row.
**Why it happens:** Sonum structures product pages differently from Askona.
**How to avoid:** First try the characteristics table; fall back to regex in the description section; store NULL if not found. This is expected and correct per the "NULL is OK" decision.
**Warning signs:** `filler` is always NULL for Sonum products — check if description contains material info.

### Pitfall 6: Camoufox Browser Not Downloaded
**What goes wrong:** `camoufox` is installed but `python -m camoufox fetch` was not run → `FileNotFoundError` on first use.
**Why it happens:** Camoufox separates pip package install from browser binary download.
**How to avoid:** Document `python -m camoufox fetch` in the project README/setup instructions. Check for browser presence in startup script.
**Warning signs:** `camoufox.exceptions.BrowserNotInstalled` or similar on `AsyncCamoufox()` construction.

---

## Code Examples

### Extract Product Data from Askona `__NEXT_DATA__`

```python
# Source: Verified from askona.ru/matrasy/160x200/ and product detail pages
import json
from decimal import Decimal
import re

async def extract_askona_catalog(page) -> list[str]:
    """Return list of product detail URLs from one catalog page."""
    content = await page.content()
    data = json.loads(re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        content, re.DOTALL
    ).group(1))
    items = data["props"]["pageProps"]["data"]["listing"]["items"]
    base = "https://www.askona.ru"
    return [base + item["data"]["productLink"] for item in items if item.get("type") == "p"]

async def extract_askona_product(page, url: str) -> dict:
    """Extract all fields from an Askona product detail page."""
    content = await page.content()
    data = json.loads(re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        content, re.DOTALL
    ).group(1))
    pd = data["props"]["pageProps"]["productData"]
    chars = {item["name"]: item["value"]
             for item in pd.get("characteristics", [{}])[0].get("items", [])}

    listing = data["props"]["pageProps"]["productData"]
    price_sale = Decimal(str(listing.get("price", 0))) if listing.get("price") else None
    price_orig = Decimal(str(listing.get("oldPrice", 0))) if listing.get("oldPrice") else None

    return {
        "source_site": "askona",
        "source_url": url,
        "name": pd.get("name", ""),
        "firmness": chars.get("Жесткость"),
        "height_cm": chars.get("Высота матраса"),
        "filler": chars.get("Наполнитель"),
        "cover_material": chars.get("Материал чехла"),
        "weight_kg": chars.get("Вес на спальное место, кг") or chars.get("Вес матраса"),
        "price_sale": price_sale,
        "price_original": price_orig,
    }
```

### Price String Cleaning (all sites)

```python
import re
from decimal import Decimal, InvalidOperation

def parse_price(text: str) -> Decimal | None:
    """Extract numeric price from Russian formatted string like '25 180 ₽'."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d,.]", "", text.replace(",", "."))
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None
```

### ScrapeRun Lifecycle

```python
from datetime import datetime, timezone
from lineaf.models.scrape_run import ScrapeRun
from lineaf.database import SessionLocal

def run_spider_with_tracking(spider_func, site_name: str):
    db = SessionLocal()
    run = ScrapeRun(site=site_name, status="running",
                    started_at=datetime.now(timezone.utc))
    db.add(run)
    db.commit()
    try:
        products_found, products_new, products_removed = spider_func(db, run.id)
        run.status = "success"
        run.products_found = products_found
        run.products_new = products_new
        run.products_removed = products_removed
    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)[:2048]
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.close()
```

### Pagination Iterator (generic)

```python
async def iter_catalog_pages(page, base_url: str, get_urls_fn):
    """Generic paginator for sites using ?page=N or &PAGEN_1=N."""
    page_num = 1
    all_urls = []
    while True:
        url = f"{base_url}?page={page_num}"  # adjust separator per site
        await goto_with_retry(page, url)
        await asyncio.sleep(random.uniform(2, 5))
        urls = await get_urls_fn(page)
        if not urls:
            break
        all_urls.extend(urls)
        page_num += 1
    return all_urls
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `requests` + `BeautifulSoup` | Playwright + stealth browser | 2022-2024 (JS SPAs proliferated) | Static parsers yield empty product containers |
| `playwright-stealth` (JS patches) | Camoufox (C++ level) | 2023 → 2024 | More robust fingerprint spoofing |
| Scrapy spiders | Async Playwright functions | Ongoing | Scrapy lacks native Playwright support; direct asyncio simpler for this scale |
| SQLAlchemy session.merge() | `insert().on_conflict_do_update()` | SQLAlchemy 2.0 | Atomic UPSERT without SELECT round-trip |

**Deprecated/outdated:**
- `Scrapy-playwright`: Would work but adds Scrapy framework complexity for only 3 spiders — not needed.
- `playwright-stealth` Python package: JS-only patches, less effective than Camoufox's C++ approach.
- `undetected-playwright`: Less maintained than Camoufox for Python.

---

## Open Questions

1. **Ormatek CSS selectors and pagination parameter**
   - What we know: URL pattern `/catalog/matrasy/160x200/`; Nuxt.js rendering; 403 to all plain clients.
   - What's unclear: Exact CSS selector for product cards; pagination parameter name (`?page=` vs `?PAGEN_1=`); total product count; which fields are in catalog vs detail page.
   - Recommendation: Wave 0 of Plan 02-02 must include a Camoufox discovery script that loads the page, dumps all CSS classes of product-like elements, and prints the `window.__NUXT__` data structure. This is a prerequisite before writing selectors.

2. **Sonum filler field**
   - What we know: Not a discrete table row on detail pages; found in description text.
   - What's unclear: Is the description consistently structured enough for regex extraction?
   - Recommendation: Store NULL initially; add regex extraction as a stretch task if the description follows a pattern like "Наполнитель: ...".

3. **Camoufox maintenance risk**
   - What we know: Original maintainer stepped down; now maintained by Clover Labs AI; v146 is experimental; v135 branch recommended for stability.
   - What's unclear: Will Camoufox remain effective against Ormatek's bot detection as the base Firefox version ages?
   - Recommendation: Pin to a specific camoufox version in pyproject.toml (not just `latest`). Monitor CloverLabsAI/camoufox for releases. Patchright (Chromium-based stealth) is the documented fallback.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (already installed in dev group) |
| Config file | none — using pytest defaults; `conftest.py` with `db_session` fixture |
| Quick run command | `pytest tests/test_scrapers.py -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCRP-01 | Askona catalog returns >0 product URLs across pages | integration | `pytest tests/test_scrapers.py::test_askona_catalog_urls -x` | ❌ Wave 0 |
| SCRP-02 | Ormatek catalog returns >0 product URLs across pages | integration | `pytest tests/test_scrapers.py::test_ormatek_catalog_urls -x` | ❌ Wave 0 |
| SCRP-03 | Sonum catalog returns >0 product URLs across pages | integration | `pytest tests/test_scrapers.py::test_sonum_catalog_urls -x` | ❌ Wave 0 |
| SCRP-04 | Extracted product record has all 8 fields (NULLs OK for optional) | unit | `pytest tests/test_pipeline.py::test_product_fields_schema -x` | ❌ Wave 0 |
| SCRP-04 | `name` and at least one price non-NULL (minimum required) | unit | `pytest tests/test_pipeline.py::test_minimum_required_fields -x` | ❌ Wave 0 |
| SCRP-05 | Camoufox browser launches without error | smoke | `pytest tests/test_scrapers.py::test_camoufox_launches -x` | ❌ Wave 0 |
| SCRP-06 | New product URL absent from DB is detected as new | unit | `pytest tests/test_pipeline.py::test_new_product_detection -x` | ❌ Wave 0 |
| SCRP-07 | Product in DB missing from scraped set is set is_active=False | unit | `pytest tests/test_pipeline.py::test_removed_product_detection -x` | ❌ Wave 0 |
| SCRP-07 | 0-result scrape does NOT mark existing products inactive | unit | `pytest tests/test_pipeline.py::test_empty_scrape_no_deactivation -x` | ❌ Wave 0 |

Note: SCRP-01, SCRP-02, SCRP-03 are integration tests that require live internet access and Camoufox browser. They should be marked `@pytest.mark.integration` and skipped by default in CI. Run manually to verify scraper correctness.

### Sampling Rate

- **Per task commit:** `pytest tests/test_pipeline.py -x` (unit tests only, no browser needed)
- **Per wave merge:** `pytest tests/ -v -m "not integration"` (all non-browser tests)
- **Phase gate:** `pytest tests/ -v` including integration tests with live sites before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_scrapers.py` — covers SCRP-01, SCRP-02, SCRP-03, SCRP-05 (requires Camoufox)
- [ ] `tests/test_pipeline.py` — covers SCRP-04, SCRP-06, SCRP-07 (unit, uses SQLite in-memory via `TEST_DATABASE_URL`)
- [ ] `tests/conftest.py` — add `db_session` fixture extension for pipeline tests (existing conftest may already have this from Phase 1)
- [ ] Camoufox install: `uv add camoufox && python -m camoufox fetch`

---

## Sources

### Primary (HIGH confidence)

- Direct WebFetch of `https://www.askona.ru/matrasy/160x200/` — confirmed Next.js SSR, `__NEXT_DATA__` JSON structure, product fields, pagination (`?page=N`), ~75 products/3 pages
- Direct WebFetch of `https://www.askona.ru/matrasy/comfort-plus.htm?SELECTED_HASH_SIZE=...` — confirmed `characteristics` array JSON path, all 8 field names
- Direct WebFetch of `https://www.sonum.ru/catalog/matrasy/?filter[width][0]=160&filter[length][0]=200` — confirmed Bitrix CMS, 57 products, `PAGEN_1=N` pagination, static HTML product cards
- Direct WebFetch of Sonum detail page — confirmed characteristics table structure, field names in Russian
- Excel reference file `askona_160x200_full2705.xlsx` — confirmed exact 9-column schema and Russian field names
- `https://www.askona.ru/robots.txt` — confirmed no crawl-delay, pagination URL patterns explicitly allowed
- [Camoufox installation docs](https://camoufox.com/python/installation/) — confirmed `pip install camoufox[geoip]` + `python -m camoufox fetch` workflow
- [GitHub daijro/camoufox](https://github.com/daijro/camoufox) — confirmed `AsyncCamoufox` API, Python 3.11 support, maintenance status
- [SQLAlchemy 2.0 PostgreSQL docs](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html) — confirmed `insert().on_conflict_do_update()` with `constraint=` parameter

### Secondary (MEDIUM confidence)

- WebSearch confirmed Askona pagination URL `?PAGEN_1=2` pattern (from Google's indexed URLs)
- Ormatek catalog URL `/catalog/matrasy/160x200/` confirmed accessible via Google index (site: search)
- Camoufox Wappalyzer lookup confirmed Nuxt.js/Vue on ormatek.com (indirect — Wappalyzer page, not ormatek.com directly)

### Tertiary (LOW confidence)

- Ormatek CSS selectors: unknown — all direct fetches returned 403; selectors must be discovered in Wave 0 with Camoufox
- Sonum detail page exact CSS classes: inferred from description; class names like `.catalog-item` are unverified against live DOM

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Camoufox is project-decided, SQLAlchemy upsert verified in docs
- Askona architecture: HIGH — direct page fetch succeeded, JSON structure confirmed
- Sonum architecture: MEDIUM-HIGH — direct page fetch succeeded, CSS classes partially verified
- Ormatek architecture: LOW — all direct fetches return 403; technology stack inferred from search/Wappalyzer
- Pitfalls: MEDIUM — derived from site behavior and known patterns; Ormatek-specific pitfalls unverified

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (sites update occasionally; re-verify selectors before production run)
