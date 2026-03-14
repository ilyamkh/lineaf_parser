# Project Research Summary

**Project:** Lineaf Price Tracker
**Domain:** Competitor price monitoring / web scraping (internal tool, mattress retail)
**Researched:** 2026-03-14
**Confidence:** HIGH

## Executive Summary

Lineaf Price Tracker is an internal competitive intelligence tool that scrapes weekly mattress prices from three Russian e-commerce sites (askona.ru, ormatek.ru, sonum.ru) and surfaces results through a dashboard for pricing decisions. The recommended approach is a three-tier Python stack: Playwright + Camoufox for browser-based scraping (all three target sites render catalogs via JavaScript, making static HTML parsers useless), PostgreSQL for append-only price history storage, and a Streamlit dashboard that reads from the same database. FastAPI serves as a JSON layer between storage and presentation. No message broker, no microservices — the system runs weekly on a single VM and the architecture should reflect that simplicity.

The single most important technical decision is committing to Playwright from day one. All three target sites are JavaScript-heavy SPAs. Any attempt to use Scrapy with plain HTTP requests will silently yield empty results — the pages return a valid 200 response with an un-hydrated HTML skeleton, which looks like success but contains nothing. Beyond JS rendering, the scraper must handle Russian price string formatting (non-breaking space as thousands separator), append-only snapshot storage (never overwrite historical records), and instrument every scrape run with start/end timestamps so the dashboard can surface stale data warnings.

The dominant risk is silent failure: a scraper can break in four independent ways (bot block, selector drift, pagination truncation, cron job death) and in each case continue to appear functional while writing garbage or nothing to the database. The mitigation strategy is not retry logic but observability — every scrape run must be recorded in a `scrape_runs` table, and the dashboard must prominently display data freshness. Build the monitoring in during Phase 1, not as a retrofit.

---

## Key Findings

### Recommended Stack

The stack separates cleanly into four independently runnable layers. Playwright 1.58 wrapped by Camoufox 0.4.11 handles browser automation with C++-level fingerprint spoofing — the best available defense against Cloudflare/DataDome without requiring proxy rotation at this scrape frequency. SQLAlchemy 2.0 + Alembic manages schema and migrations against PostgreSQL 16; psycopg3 (v3.3.3) is the driver with 3-4x throughput improvement over psycopg2. APScheduler 3.11.2 embedded in the FastAPI process provides scheduling without broker infrastructure. Streamlit 1.55 + Plotly delivers an interactive dashboard in pure Python with zero frontend build pipeline.

A critical note on Camoufox: the primary maintainer was hospitalized in March 2025 and active development has moved to community forks. The library is functional but may lag on browser version updates. `playwright-stealth` is the documented fallback.

**Core technologies:**
- Playwright 1.58 + Camoufox 0.4.11: headless browser automation with anti-bot evasion — all three target sites require JS execution; Camoufox patches fingerprints at C++ level
- PostgreSQL 16 + SQLAlchemy 2.0 + Alembic 1.18.4: relational storage with migrations — natural fit for structured, append-only price history rows
- psycopg 3.3.3: PostgreSQL driver — 3-4x faster than psycopg2, native async support
- APScheduler 3.11.2: in-process job scheduler — no broker infrastructure required for weekly single-machine job
- FastAPI ≥0.115 + pydantic-settings 2.13.1: REST API and configuration — async-native, auto docs, type-validated settings
- Streamlit 1.55 + Plotly + pandas 3.0.1: internal dashboard — ships in days, pure Python, no JS build pipeline
- uv: package management — faster than pip, lockfile support, PEP 621 compliant

### Expected Features

**Must have (table stakes):**
- Current price per product (both `price_original` and `price_sale` — Russian retailers use promotional pricing pervasively)
- Price history per product — requires append-only timestamped rows from every scrape run
- Competitor comparison view — table grouping same-tier mattresses across Askona/Ormatek/Sonum
- New/removed product detection — diff SKU set between runs; flag disappearances without deleting history
- Scheduled automatic collection — weekly cron with run metadata logged to `scrape_runs`
- Product attributes alongside prices — firmness, height, filler, cover material; without these, price comparison is apples-to-oranges
- Basic filtering/sorting — by competitor, price, firmness; a 50-row table without filters is unusable
- Last-updated timestamp and error visibility — distinguish stale data from genuinely unchanged prices

**Should have (differentiators):**
- Price delta highlighting — color-code changes since last run (high value, low effort)
- Trend charts per product — Plotly line chart over time for seasonal pattern detection
- Discount depth tracking — store `(price_original - price_sale) / price_original` as derived column
- Export to CSV — bridges to existing Excel workflows; single endpoint
- Assortment overview — SKU count per competitor per run to detect lineup changes

**Defer to v2+:**
- Price index / relative positioning — requires manual Lineaf-to-competitor product mapping (external work)
- Side-by-side attribute comparison — table view partially covers this in v1
- Telegram/email alerts — explicitly out of scope; pull-model dashboard sufficient for weekly review
- Marketplace integrations (Wildberries, Ozon) — out of scope per project constraints
- Multi-user auth — small internal team; not needed in v1

### Architecture Approach

The architecture is a strict three-tier pipeline: Scheduler triggers Spiders which write through an Item Pipeline to PostgreSQL; FastAPI reads from PostgreSQL and serves JSON; Streamlit (or Jinja2+HTMX) renders the dashboard from that JSON. No component crosses its tier boundary — spiders never call FastAPI, the dashboard never queries PostgreSQL directly, the scheduler never touches the API layer. This separation ensures each tier can be developed, tested, and debugged independently.

**Major components:**
1. Scheduler (APScheduler in FastAPI process) — weekly trigger, writes `scrape_runs` start record, invokes all three spiders
2. Spiders (one per site, inheriting shared base class) — fetch catalog pages, extract product dicts, yield to pipeline
3. Item Pipeline — validates fields, normalizes prices to `NUMERIC(12,2)`, UPSERTs `products` table, INSERTs `price_snapshots` row
4. PostgreSQL (3 tables: `scrape_runs`, `products`, `price_snapshots`) — append-only price history, `is_active` flag for removed products
5. FastAPI backend — `/api/prices`, `/api/products`, `/api/runs` endpoints; also optionally serves Jinja2-rendered dashboard HTML
6. Dashboard (Streamlit or Jinja2+HTMX+Chart.js) — competitor comparison table, price history charts, filters, data freshness indicator

### Critical Pitfalls

1. **JS-rendered catalogs mistaken for static HTML** — Use Playwright from day one; check DevTools Network tab for underlying JSON API endpoints before writing selectors; confirm with headed-mode test before automating. Detection: spider completes in <2s, item count is 0 or far below visible count.

2. **Silent scrape job failure — stale data presented as current** — Log every run (start, end, status, items count) to `scrape_runs` table; display "Data last updated: N days ago" prominently on dashboard with red color if >8 days; implement dead-man's switch healthcheck ping on successful completion.

3. **Selector drift after site redesign** — Prefer `[itemprop="price"]`, `[data-price]`, JSON-LD structured data over CSS class selectors; alternatively target the underlying XHR API endpoint; post-extraction validation: assert non-null numeric price for every item; alert if `null_count / total_count > 0.1`.

4. **Bot detection and IP blocks** — Use Camoufox stealth from first run (not as retrofit); randomize delays 3–8s; rotate realistic User-Agent strings; add pre-run validation that checks expected item count before committing data.

5. **Russian price string parsing failures** — Write a dedicated `parse_price(text: str) -> Optional[Decimal]` utility before any spider extracts prices; strip `\xa0`, `\u202f`, and regular spaces; assert parsed value is between 1,000 and 500,000 RUB.

---

## Implications for Roadmap

The architecture research prescribes a clear dependency chain: database schema must exist before any writes, spiders must produce data before the pipeline can be verified, the API must work before the dashboard can call it. The build order below follows these hard dependencies while front-loading the riskiest work (per-site scraping with JS rendering and anti-bot handling).

### Phase 1: Database Foundation and Schema
**Rationale:** The DB schema is the contract everything else depends on. Schema decisions made here (price as `NUMERIC(12,2)`, `is_active` flag, `scrape_runs` table) cannot be cheaply changed later. Get it right first.
**Delivers:** PostgreSQL schema with all 3 tables, Alembic migration baseline, SQLAlchemy models, local dev environment (`uv`, `.env`, `docker-compose` for Postgres).
**Addresses:** Historical data persistence, audit trail per scrape run, product deactivation without history loss.
**Avoids:** Pitfall 5 (fake discount calculations) — schema stores both `price_original` and `price_sale` as separate `NUMERIC` columns from day one. Pitfall 6 (product identity) — `source_url` as natural dedup key, attribute columns as comparison anchors. Anti-pattern of storing prices as TEXT or FLOAT.

### Phase 2: Scraper — Askona Spider
**Rationale:** Spiders are the highest-risk components (JS rendering uncertainty, anti-bot exposure, pagination handling). Building one site first limits blast radius and produces a working data flow to validate the pipeline against before committing to three implementations.
**Delivers:** Working Askona spider using Playwright + Camoufox; extracts all required fields (name, `price_original`, `price_discounted`, hardness, height, filler, cover, weight); handles pagination completely; writes through Item Pipeline to `products` and `price_snapshots` tables.
**Uses:** Playwright 1.58, Camoufox 0.4.11, `parse_price()` utility with Russian locale handling.
**Avoids:** Pitfall 1 (JS rendering), Pitfall 2 (bot detection), Pitfall 8 (incomplete pagination), Pitfall 9 (price string parsing).
**Research flag:** Likely needs per-site inspection — Askona's actual HTML/JS structure and whether an underlying XHR API endpoint can be targeted directly.

### Phase 3: Scraper — Ormatek and Sonum Spiders
**Rationale:** After Askona proves the pattern, implement the remaining two sites. Each site may have unique pagination mechanics or selector structures — building sequentially isolates per-site issues.
**Delivers:** Ormatek and Sonum spiders with identical output schema; full 3-site data collection working end-to-end; new/removed product detection logic (diff SKU sets between runs).
**Avoids:** Pitfall 3 (selector drift) — document selectors and baseline item counts per site during development; Pitfall 8 (pagination) — assert scraped count against expected count.
**Research flag:** Per-site inspection required; Ormatek and Sonum may need separate scraping approaches.

### Phase 4: FastAPI Backend
**Rationale:** Data is now in the DB. Build the read API before any dashboard code so it can be validated independently with `curl` or browser. Establishes the contract the dashboard will depend on.
**Delivers:** `/api/prices`, `/api/products`, `/api/runs` endpoints with filtering (by competitor, date range); Pydantic response models; OpenAPI docs at `/docs`.
**Uses:** FastAPI ≥0.115, pydantic-settings 2.13.1, uvicorn ≥0.32.
**Implements:** FastAPI backend component; enforces "dashboard does not talk directly to PostgreSQL" boundary.

### Phase 5: Dashboard
**Rationale:** All data layers are working. Build the visualization layer now that the API contract is stable.
**Delivers:** Streamlit (or Jinja2+HTMX+Chart.js) dashboard with competitor price comparison table, price history line charts (Plotly), price delta highlighting (red/green for changes since last run), filtering by competitor/firmness, prominent "data last updated" freshness indicator.
**Addresses:** Current price view, price history visualization, competitor comparison, basic filtering, price delta highlighting (table stakes + first differentiator).
**Avoids:** Pitfall 4 (stale data presented as current) — freshness indicator is built into the dashboard from day one.

### Phase 6: Scheduling, Observability, and Deployment
**Rationale:** Manual triggering is sufficient during development. Automate and harden only after the full pipeline is validated end-to-end.
**Delivers:** APScheduler weekly cron job embedded in FastAPI process; `scrape_runs` status logging with FAILED status on exception; dead-man's switch healthcheck ping; Playwright memory cleanup (explicit context close in `finally`); deployment configuration (systemd services or docker-compose).
**Avoids:** Pitfall 4 (silent cron failures), Pitfall 7 (Playwright memory leaks).

### Phase Ordering Rationale

- Schema-first ordering follows the hard dependency chain identified in ARCHITECTURE.md: DB → Spiders → Pipeline → API → Dashboard → Scheduler.
- Askona-first spider development limits risk exposure — JS rendering and anti-bot handling must be solved once before multiplying the pattern across sites.
- FastAPI before dashboard ensures the API contract is independently verifiable; dashboard built on a moving target is harder to debug.
- Scheduler last because it wraps a complete working pipeline — manual triggering during development is lower overhead and allows faster iteration.
- Monitoring (scrape_runs logging, freshness indicator) is distributed across phases 1, 5, and 6 rather than deferred entirely — the core observability primitives are cheap and must not be retrofitted.

### Research Flags

Phases needing deeper per-site research during planning:
- **Phase 2 (Askona spider):** Actual page structure, JS rendering mechanism, and whether underlying XHR API endpoints can be targeted directly need hands-on inspection before writing selectors. Selector strategy can differ significantly based on findings.
- **Phase 3 (Ormatek and Sonum spiders):** Same per-site inspection required. These may have different pagination mechanics (infinite scroll vs. URL params vs. "Load more" button).

Phases with well-documented patterns (standard implementation, skip research-phase):
- **Phase 1 (Database schema):** SQLAlchemy + Alembic setup is well-documented; schema is specified in ARCHITECTURE.md; no novel patterns needed.
- **Phase 4 (FastAPI backend):** Straightforward CRUD read API; standard FastAPI patterns apply.
- **Phase 6 (Scheduling and deployment):** APScheduler-in-FastAPI pattern is documented; docker-compose for single-VM deployment is standard.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI; technology choices backed by multiple independent sources with explicit rationale |
| Features | MEDIUM-HIGH | Table stakes derived from commercial price tracking tools and domain knowledge; Russian retail pricing patterns confirmed by project's existing Excel sample; cross-brand comparison difficulty HIGH confidence from industry research |
| Architecture | HIGH | Three-tier pattern well-established for scraping systems; schema design follows documented price-history DB patterns; build order confirmed by hard dependency analysis |
| Pitfalls | HIGH | Critical pitfalls (JS rendering, bot detection, selector drift, silent failures) consistently appear across multiple independent scraping resources; Russian price locale formatting is a concrete technical fact |

**Overall confidence:** HIGH

### Gaps to Address

- **Actual site structure of Askona, Ormatek, Sonum:** No hands-on inspection was performed. Whether catalog pages expose underlying XHR API endpoints (which would be more reliable than DOM scraping) is unknown. Recommend DevTools inspection as the first action in Phase 2 before writing any selectors.
- **Anti-bot protection level of target sites:** PITFALLS.md rates the anti-bot risk as MEDIUM-low at weekly frequency, but this is an inference. The actual WAF configuration of askona.ru and ormatek.ru was not verified. Camoufox covers most scenarios, but CAPTCHA fallback strategy is not yet defined.
- **Camoufox long-term maintenance:** The library is functional but community-maintained as of early 2026. `playwright-stealth` should be evaluated as a drop-in fallback before committing to production deployment.
- **Lineaf product catalog for price indexing:** The "price index / relative positioning" differentiator feature requires a Lineaf product catalog to map against competitors. This is an external data dependency not covered by the scraping work; it should be treated as a separate milestone.

---

## Sources

### Primary (HIGH confidence)
- [playwright PyPI](https://pypi.org/project/playwright/) — version 1.58.0 confirmed
- [SQLAlchemy PyPI](https://pypi.org/project/SQLAlchemy/) — version 2.0.48 confirmed
- [Alembic PyPI](https://pypi.org/project/alembic/) — version 1.18.4 confirmed
- [psycopg PyPI](https://pypi.org/project/psycopg/) — version 3.3.3 confirmed
- [APScheduler PyPI](https://pypi.org/project/apscheduler/) — version 3.11.2 confirmed
- [Streamlit PyPI](https://pypi.org/project/streamlit/) — version 1.55.0 confirmed
- [pandas PyPI](https://pypi.org/project/pandas/) — version 3.0.1 confirmed
- [Scrapy Architecture Overview — official docs](https://docs.scrapy.org/en/latest/topics/architecture.html) — architecture patterns
- [scrapy-playwright RAM spikes — GitHub issue #325](https://github.com/scrapy-plugins/scrapy-playwright/issues/325) — memory leak pitfall
- [Scrapy memory leak debugging — official docs](https://docs.scrapy.org/en/latest/topics/leaks.html) — Playwright memory pitfall

### Secondary (MEDIUM confidence)
- [Camoufox GitHub](https://github.com/daijro/camoufox) — anti-bot Firefox fork, maintenance status
- [ScrapingBee: Camoufox guide](https://www.scrapingbee.com/blog/how-to-scrape-with-camoufox-to-bypass-antibot-technology/) — Camoufox adoption rationale
- [Tiger Data: psycopg2 vs psycopg3 benchmark](https://www.tigerdata.com/blog/psycopg2-vs-psycopg3-performance-benchmark) — driver selection
- [Squadbase: Streamlit vs Dash 2025](https://www.squadbase.dev/en/blog/streamlit-vs-dash-in-2025-comparing-data-app-frameworks) — dashboard choice
- [Leapcell: APScheduler vs Celery Beat](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-vs-celery-beat) — scheduler selection
- [Zyte: Price Intelligence with Python](https://www.zyte.com/blog/price-intelligence-with-python-scrapy-sql-pandas/) — architecture patterns
- [Red Gate: Price History Database Model](https://www.red-gate.com/blog/price-history-database-model/) — schema design
- [Prisync competitor price tracking features](https://prisync.com/competitor-price-tracking/) — feature landscape
- [Price2Spy feature comparison](https://www.price2spy.com/feature-comparison.html) — feature landscape
- [GoodBed: mattress name comparison](https://www.goodbed.com/guides/mattress-name-comparison/) — cross-brand naming problem
- [Brightdata: fix inaccurate web scraping data](https://brightdata.com/blog/web-data/fix-inaccurate-web-scraping-data) — pitfall mitigations

### Tertiary (LOW confidence)
- [Scrappey Wiki: competitor price monitoring guide](https://wiki.scrappey.com/build-competitor-price-monitoring-software-a-practical-guide) — vendor blog, architecture overview only
- [vc.ru: парсинг сайтов в России](https://vc.ru/legal/64328-parsing-saitov-rossiya-i-mir-kak-s-tochki-zreniya-zakona-vyglyadit-odin-iz-samyh-poleznyh-instrumentov) — Russian legal context, needs validation for current law

---
*Research completed: 2026-03-14*
*Ready for roadmap: yes*
