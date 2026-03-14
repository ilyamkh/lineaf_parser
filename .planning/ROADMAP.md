# Roadmap: Lineaf Price Tracker

## Overview

Three phases follow the hard dependency chain dictated by the architecture: the database schema is the contract everything writes to; scrapers produce the data; the API + dashboard + scheduler deliver the value to the team. Phase 1 establishes the foundation, Phase 2 fills it with data from all three competitors, Phase 3 surfaces that data as an actionable dashboard running on autopilot.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Foundation** - Project scaffold, PostgreSQL schema, dev environment
- [ ] **Phase 2: Scrapers** - Playwright spiders for all three sites, full data collection pipeline
- [ ] **Phase 3: Dashboard** - FastAPI backend, Streamlit dashboard, scheduling, deployment

## Phase Details

### Phase 1: Foundation
**Goal**: The database schema exists and the dev environment runs locally, so every subsequent phase can write and read data against a stable contract.
**Depends on**: Nothing (first phase)
**Requirements**: STOR-01, STOR-02, STOR-03, STOR-04
**Success Criteria** (what must be TRUE):
  1. `docker-compose up` starts a local PostgreSQL instance and the app connects to it without errors
  2. All three tables (`products`, `price_snapshots`, `scrape_runs`) exist with correct columns and types after running Alembic migrations
  3. A manual test insert of a product + price snapshot round-trips correctly through SQLAlchemy models
  4. `is_active` flag exists on `products`; both `price_original` and `price_sale` are stored as `NUMERIC(12,2)`, not float or text
**Plans**: 2 plans

Plans:
- [ ] 01-01-PLAN.md — Project scaffold (uv, pyproject.toml, .env, docker-compose, config, database, Alembic init)
- [ ] 01-02-PLAN.md — SQLAlchemy models + Alembic migration + test suite for STOR-01 through STOR-04

### Phase 2: Scrapers
**Goal**: All three competitor sites are scraped automatically, producing complete, validated product records in the database, with new and removed products correctly detected.
**Depends on**: Phase 1
**Requirements**: SCRP-01, SCRP-02, SCRP-03, SCRP-04, SCRP-05, SCRP-06, SCRP-07
**Success Criteria** (what must be TRUE):
  1. Running the Askona spider inserts all 160×200 mattresses with non-null values for model, price_sale, price_original, firmness, height, filler, cover material, and weight per sleeping place
  2. Running the Ormatek and Sonum spiders produces equivalent complete records — all required fields populated, all catalog pages covered (no pagination truncation)
  3. Running the scraper twice in a row: second run detects zero new products and zero removed products when the catalog hasn't changed
  4. Removing a product from the catalog (simulated) causes the spider to set `is_active = false` on that product without deleting its price history
  5. The `scrape_runs` table records a row for each run with start time, end time, item count, and success/failure status
**Plans**: TBD

Plans:
- [ ] 02-01: Askona spider (Playwright + Camoufox, pagination, field extraction, price parsing utility)
- [ ] 02-02: Ormatek spider (adapt pattern, handle site-specific pagination and selectors)
- [ ] 02-03: Sonum spider (adapt pattern, handle site-specific pagination and selectors)
- [ ] 02-04: Item pipeline (field validation, price normalization, UPSERT products, INSERT price_snapshots, new/removed detection, scrape_runs logging)

### Phase 3: Dashboard
**Goal**: The team can open a browser, see current competitor prices and their history, and the system collects new data automatically every week without manual intervention.
**Depends on**: Phase 2
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06, SCHD-01, SCHD-02
**Success Criteria** (what must be TRUE):
  1. A team member opens the dashboard URL and sees a filterable table of current prices grouped by competitor, with the last-updated timestamp prominently displayed in red if data is more than 8 days old
  2. Selecting a product shows a line chart of its price history over all collected weeks
  3. The dashboard shows a list of products that appeared or disappeared since the last scrape run
  4. Clicking "Export" downloads a CSV/Excel file containing all current price data
  5. The scraper runs automatically every week without manual triggering; the run log (success/failure, item count) is visible in the dashboard
**Plans**: TBD

Plans:
- [ ] 03-01: FastAPI backend (/api/prices, /api/products, /api/runs endpoints with filtering)
- [ ] 03-02: Streamlit dashboard (competitor table, price history charts, freshness indicator, new/removed list, export)
- [ ] 03-03: APScheduler weekly cron + deployment config (systemd or docker-compose for VM)

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 0/2 | Not started | - |
| 2. Scrapers | 0/4 | Not started | - |
| 3. Dashboard | 0/3 | Not started | - |
