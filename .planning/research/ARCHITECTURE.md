# Architecture Patterns

**Domain:** Competitor price tracking / web scraping system
**Project:** Lineaf Price Tracker
**Researched:** 2026-03-14
**Confidence:** HIGH (patterns well-established, verified across multiple authoritative sources)

---

## Recommended Architecture

A three-tier architecture with clear separation between data collection, storage, and presentation.
No microservices — this system is internal, small-team, and runs weekly, not real-time.

```
┌─────────────────────────────────────────────────────────────────┐
│                        SCHEDULER                                │
│                    (APScheduler / cron)                         │
│              Weekly trigger → runs all 3 spiders                │
└─────────────────────────┬───────────────────────────────────────┘
                          │ triggers
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
  │  Spider:      │ │  Spider:      │ │  Spider:      │
  │  Askona       │ │  Ormatek      │ │  Sonum        │
  │  (Playwright) │ │  (Playwright) │ │  (Playwright) │
  └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │ normalized product dicts
                            ▼
                  ┌─────────────────┐
                  │  Item Pipeline  │
                  │  (validation,   │
                  │   dedup, upsert)│
                  └────────┬────────┘
                           │ SQL writes
                           ▼
                  ┌─────────────────┐
                  │   PostgreSQL    │
                  │                 │
                  │  products       │
                  │  price_snapshots│
                  │  scrape_runs    │
                  └────────┬────────┘
                           │ SQL reads
                           ▼
                  ┌─────────────────┐
                  │   FastAPI       │
                  │   backend       │
                  │                 │
                  │  /api/prices    │
                  │  /api/products  │
                  │  /api/runs      │
                  └────────┬────────┘
                           │ JSON / HTML
                           ▼
                  ┌─────────────────┐
                  │  Web Dashboard  │
                  │  Jinja2 + HTMX  │
                  │  + Chart.js     │
                  └─────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | Consumes | Produces |
|-----------|---------------|----------|----------|
| **Scheduler** | Triggers weekly scrape runs | Time/cron | Spider invocations |
| **Spider: Askona** | Crawls askona.ru catalog 160x200, extracts product fields | HTTP/browser | Raw product dicts |
| **Spider: Ormatek** | Crawls ormatek.ru catalog 160x200, extracts product fields | HTTP/browser | Raw product dicts |
| **Spider: Sonum** | Crawls sonum.ru catalog 160x200, extracts product fields | HTTP/browser | Raw product dicts |
| **Item Pipeline** | Validates fields, normalizes prices (Decimal), writes to DB | Raw product dicts | DB rows |
| **PostgreSQL** | Stores product catalog, price snapshots, run metadata | SQL writes | SQL reads |
| **FastAPI backend** | Serves JSON API and optional server-rendered pages | DB reads | JSON / HTML |
| **Dashboard (frontend)** | Visualizes prices, history, competitor comparison | JSON from FastAPI | Browser UI |

### What does NOT talk to what

- Spiders do NOT talk to FastAPI (no circular loops)
- Dashboard does NOT talk directly to PostgreSQL (always through FastAPI)
- Scheduler does NOT touch FastAPI (it invokes spiders directly)

---

## Data Flow

### Scrape Flow (weekly, automated)

```
1. Scheduler fires (weekly cron or APScheduler interval trigger)
2. Creates a scrape_run record (start_time, status=running)
3. Launches each spider sequentially or in parallel
4. Each spider:
   a. Fetches category page (paginated)
   b. For each product card: extracts URL, name, price_original,
      price_discounted, hardness, height, filler, cover_material, weight
   c. Yields product dict to Item Pipeline
5. Item Pipeline for each item:
   a. Validates required fields present
   b. Normalizes price strings → Decimal
   c. UPSERT products table (keyed by source_url)
   d. INSERT price_snapshots row (timestamped)
   e. Detects new vs existing products (for catalog tracking)
6. Updates scrape_run record (end_time, status=done, items_count)
```

### Read Flow (dashboard user)

```
1. User opens dashboard in browser
2. Browser → GET /dashboard → FastAPI returns HTML (Jinja2 template)
3. Browser → GET /api/prices?competitor=all&date_from=...
4. FastAPI → SQL query on price_snapshots JOIN products
5. FastAPI → returns JSON array
6. Chart.js renders price comparison charts
7. User can filter by competitor, date range, product
```

---

## Database Schema

Three tables cover all requirements. Keep it minimal.

### `scrape_runs`
Tracks each execution for observability.

```sql
CREATE TABLE scrape_runs (
    id          SERIAL PRIMARY KEY,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    status      VARCHAR(20) NOT NULL DEFAULT 'running',  -- running | done | failed
    items_count INTEGER DEFAULT 0,
    error_msg   TEXT
);
```

### `products`
One row per unique product URL. Deduplicates across runs.

```sql
CREATE TABLE products (
    id              SERIAL PRIMARY KEY,
    source          VARCHAR(50) NOT NULL,   -- 'askona' | 'ormatek' | 'sonum'
    source_url      TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,  -- goes FALSE if disappears from catalog
    first_seen_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### `price_snapshots`
One row per product per scrape run. All mutable fields captured here.

```sql
CREATE TABLE price_snapshots (
    id                  SERIAL PRIMARY KEY,
    product_id          INTEGER NOT NULL REFERENCES products(id),
    scrape_run_id       INTEGER NOT NULL REFERENCES scrape_runs(id),
    scraped_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    price_original      NUMERIC(12,2),      -- цена до скидки
    price_discounted    NUMERIC(12,2),      -- цена после скидки
    hardness            TEXT,               -- жёсткость
    height_cm           NUMERIC(5,1),       -- высота
    filler              TEXT,               -- наполнитель
    cover_material      TEXT,               -- материал чехла
    weight_kg           NUMERIC(6,2)        -- вес на спальное место
);

CREATE INDEX ON price_snapshots (product_id, scraped_at DESC);
CREATE INDEX ON price_snapshots (scrape_run_id);
```

### Key schema decisions

- `source_url` as natural key for deduplication — survives renames
- All prices as `NUMERIC(12,2)` not FLOAT — avoids floating point drift
- `is_active` flag on products — detects removed listings without deleting history
- `scrape_run_id` on every snapshot — supports full audit trail per run

---

## Patterns to Follow

### Pattern 1: Item Pipeline for DB writes

Write all database interaction in a Scrapy Item Pipeline class, not inside the spider.
Keeps spiders pure (fetch + extract only), pipelines pure (validate + persist only).

```python
class PostgresPipeline:
    def open_spider(self, spider):
        self.conn = psycopg2.connect(settings.DATABASE_URL)

    def process_item(self, item, spider):
        # upsert product, insert snapshot
        ...
        return item

    def close_spider(self, spider):
        self.conn.close()
```

### Pattern 2: Spider-per-site

One Python file per competitor site. Each inherits from a base class with shared
extraction utilities (price normalization, field cleaning). This makes it easy to
add a 4th competitor later without touching existing spiders.

```python
class BaseMatressSpider(scrapy.Spider):
    def normalize_price(self, raw: str) -> Decimal: ...

class AskonaSpider(BaseMatressSpider):
    name = "askona"
    start_urls = ["https://www.askona.ru/mattresses/?size=160x200"]
```

### Pattern 3: APScheduler embedded in FastAPI

APScheduler runs inside the same FastAPI process. No separate broker (no Redis,
no RabbitMQ). At the scale of 3 sites weekly, this is correct — Celery would be
over-engineering.

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def start_scheduler():
    scheduler.add_job(run_scrape, "cron", day_of_week="mon", hour=6)
    scheduler.start()
```

### Pattern 4: Server-rendered dashboard with Jinja2 + HTMX

FastAPI renders HTML pages via Jinja2 templates. Chart.js draws charts from JSON
API endpoints. HTMX for filter interactions (no full React build pipeline needed).
This cuts frontend complexity dramatically for an internal tool used by a small team.

```
GET /dashboard          → HTML page (Jinja2 template)
GET /api/prices         → JSON data for Chart.js
GET /api/products       → JSON product list
GET /api/runs           → JSON scrape run history
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Storing prices as TEXT or FLOAT

**What goes wrong:** "4 990 руб." stored as text, or 4990.00000000001 from float arithmetic.
**Why bad:** Impossible to sort, aggregate, or compare reliably.
**Instead:** Strip formatting in the pipeline, store as `NUMERIC(12,2)`.

### Anti-Pattern 2: One giant spider for all sites

**What goes wrong:** Single spider tries to handle 3 different HTML structures.
**Why bad:** Any site change breaks all 3, impossible to test in isolation.
**Instead:** Spider-per-site with a shared base class.

### Anti-Pattern 3: Deleting products that disappear from catalog

**What goes wrong:** Product no longer appears in crawl → pipeline deletes DB row.
**Why bad:** Loses all price history. Can't tell if product was discontinued or just moved.
**Instead:** Set `is_active = FALSE`, preserve all history.

### Anti-Pattern 4: Celery + Redis for weekly 3-site scraping

**What goes wrong:** Team adds Redis, Celery workers, Flower monitoring for 3 jobs/week.
**Why bad:** Massive operational overhead for trivial task volume.
**Instead:** APScheduler embedded in FastAPI process. Add Celery only if volume grows 100x.

### Anti-Pattern 5: Scrapy for JavaScript-heavy pages without browser

**What goes wrong:** Scrapy fetches HTML, prices are rendered client-side → empty results.
**Why bad:** Russian retail sites (Askona, Ormatek) frequently use JS rendering.
**Instead:** Use `scrapy-playwright` integration or pure Playwright; validate with actual page inspection first.

---

## Build Order (Phase Dependencies)

Dependencies flow strictly top-to-bottom. Each phase can be tested independently.

```
Phase 1: Database + Schema
    ↓ (DB must exist before any writes)
Phase 2: Spiders (one site at a time)
    ↓ (spiders must produce data before pipeline can be verified)
Phase 3: Item Pipeline + DB writes
    ↓ (data must be in DB before API can serve it)
Phase 4: FastAPI backend (read API)
    ↓ (API must exist before dashboard can call it)
Phase 5: Web Dashboard (Jinja2 + Chart.js)
    ↓ (everything above must work before scheduling makes sense)
Phase 6: Scheduler + automation
```

**Rationale for this order:**
- DB schema is the contract everything else depends on — get it right first
- Spiders are the riskiest components (site structure may vary, JS rendering uncertainty) — build early to discover anti-scraping issues
- One spider per phase iteration (Askona → Ormatek → Sonum) reduces blast radius of per-site surprises
- FastAPI before dashboard — can test API with curl before building UI
- Scheduler last — can trigger manually during development, automate when everything works

---

## Scalability Considerations

At Lineaf's scale (3 sites, weekly, ~100-500 products each), this architecture
is intentionally simple. Notes for future scaling:

| Concern | Current scale (3 sites/week) | If 10+ sites or daily runs |
|---------|------------------------------|---------------------------|
| Scheduling | APScheduler in-process | Move to Celery + Redis |
| DB volume | Single PostgreSQL instance | Add TimescaleDB extension for time-series |
| Anti-bot | Playwright + basic delays | Add rotating residential proxies |
| Frontend | Jinja2 SSR + Chart.js | Consider React if interactions grow |
| Deployment | Single VM, single process | Docker Compose (scraper + api + db) |

---

## Sources

- [Scrapy Architecture Overview — Scrapy 2.14 docs](https://docs.scrapy.org/en/latest/topics/architecture.html) — HIGH confidence (official)
- [Price Intelligence with Python: Scrapy, SQL, Pandas — Zyte](https://www.zyte.com/blog/price-intelligence-with-python-scrapy-sql-pandas/) — MEDIUM confidence
- [APScheduler vs Celery Beat — Leapcell](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-vs-celery-beat) — MEDIUM confidence
- [FastAPI Templating Jinja2 + HTMX — johal.in 2025](https://www.johal.in/fastapi-templating-jinja2-server-rendered-ml-dashboards-with-htmx-2025-3/) — MEDIUM confidence
- [Designing a Price History Database Model — Red Gate](https://www.red-gate.com/blog/price-history-database-model/) — MEDIUM confidence
- [Scrapy vs Playwright — Bright Data](https://brightdata.com/blog/web-data/scrapy-vs-playwright) — MEDIUM confidence
- [Build Competitor Price Monitoring Software — Scrappey Wiki](https://wiki.scrappey.com/build-competitor-price-monitoring-software-a-practical-guide) — LOW confidence (vendor blog)
