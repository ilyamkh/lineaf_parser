# Phase 3: Dashboard & Scheduling - Context

**Gathered:** 2026-03-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Streamlit dashboard for the team to view competitor prices, price history charts, new/removed products, and export data. FastAPI backend as API layer. APScheduler for weekly auto-scraping + manual trigger button in dashboard.

</domain>

<decisions>
## Implementation Decisions

### Внешний вид (Layout & Design)
- Language: Russian — all labels, headers, buttons in Russian
- Claude's Discretion: layout (single page vs tabs), main screen structure, color scheme
- Claude's Discretion: whether to use overview panel with KPI metrics at top

### Графики цен (Price Charts)
- Three chart types required:
  1. **Динамика товара** — line chart of a specific product's price over weeks
  2. **Сравнение конкурентов** — average price per competitor over time
  3. **Распределение цен** — histogram/box-plot of prices per competitor
- Price shown on charts: **price_sale** (after discount) — the real purchase price
- Claude's Discretion: chart library (Plotly, Altair, etc.), period selector, interactivity

### Автозапуск (Scheduling)
- Weekly auto-scrape: Claude picks optimal low-load time (e.g., Monday 3:00 AM)
- Manual trigger: "Запустить парсинг" button in the dashboard
- Error handling: Claude's Discretion (red indicator if data >8 days old is already in requirements)

### Claude's Discretion
- Dashboard framework details (Streamlit layout, components)
- FastAPI endpoint structure
- APScheduler configuration
- Chart library and interactivity level
- Tab vs single-page layout

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Product` model with source_site, name, firmness, height_cm, filler, cover_material, weight_kg, is_active
- `PriceSnapshot` model with price_sale, price_original, product_id, scrape_run_id, scraped_at
- `ScrapeRun` model with site, status, started_at, finished_at, products_found, products_new, products_removed
- `database.py`: SessionLocal, get_db() — ready for FastAPI dependency injection
- `run_scrapers.py`: entry point for all 3 scrapers — can be called from dashboard button
- 207 products already in DB (75 Askona, 75 Ormatek, 57 Sonum)

### Established Patterns
- SQLAlchemy 2.0 Mapped[] style
- pydantic-settings for configuration
- Docker Compose for PostgreSQL

### Integration Points
- Dashboard reads from products, price_snapshots, scrape_runs tables
- Manual scrape button calls run_scrapers.py as subprocess
- APScheduler embedded in FastAPI process
- Freshness indicator queries scrape_runs for latest successful run per site

</code_context>

<specifics>
## Specific Ideas

- User wants both automatic (cron) and manual (button) scrape triggers
- Charts show price_sale only (not price_original)
- All UI in Russian
- Team of several people will use this — needs to be accessible via URL

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-dashboard*
*Context gathered: 2026-03-15*
