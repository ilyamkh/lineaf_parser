---
phase: 03-dashboard
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, pandas, openpyxl, rest-api, excel-export]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: "SQLAlchemy models (Product, PriceSnapshot, ScrapeRun), database.py get_db"
  - phase: 02-scrapers
    provides: "Data in database to query against"
provides:
  - "7 REST API endpoints for dashboard consumption"
  - "Price current/history/index/export endpoints"
  - "Run log and freshness endpoints"
  - "Product change detection endpoint"
affects: [03-dashboard]

# Tech tracking
tech-stack:
  added: [httpx, streamlit, apscheduler, plotly, requests]
  patterns: [FastAPI APIRouter with prefix, dependency-injected DB sessions, Decimal-to-float casting at query boundary, StaticPool for SQLite test isolation]

key-files:
  created:
    - src/lineaf/api/__init__.py
    - src/lineaf/api/prices.py
    - src/lineaf/api/products.py
    - src/lineaf/api/runs.py
    - tests/test_api.py
  modified:
    - src/lineaf/main.py
    - pyproject.toml

key-decisions:
  - "StaticPool for SQLite in-memory test DB to share single connection across all sessions"
  - "Naive datetime timezone handling: assume UTC when SQLite strips tzinfo for comparison operations"
  - "Max snapshot ID subquery for latest-per-product (deterministic, avoids ties on scraped_at)"

patterns-established:
  - "API router pattern: separate module per domain (prices, products, runs) with include_router prefix=/api"
  - "Decimal casting: all SQLAlchemy Decimal/Numeric values explicitly float() at serialization boundary"
  - "Test pattern: module-level engine with StaticPool, autouse seed fixture with teardown"

requirements-completed: [DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06, SCHD-02]

# Metrics
duration: 3min
completed: 2026-03-15
---

# Phase 03 Plan 01: REST API Endpoints Summary

**7 FastAPI endpoints for prices (current/history/index/export), scrape runs (log/freshness), and product change detection with full test coverage**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-15T05:16:34Z
- **Completed:** 2026-03-15T05:20:32Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 7

## Accomplishments
- 7 API endpoints operational and tested (8 test cases, all passing)
- Excel export produces valid .xlsx via pandas + openpyxl
- All Decimal fields returned as float in JSON responses
- Site filtering on /api/prices works correctly
- Freshness endpoint identifies stale data (>8 days since last successful run)
- New/removed product detection with configurable 8-day window

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for API endpoints** - `f68f410` (test)
2. **Task 1 (GREEN): Implement all 7 API endpoints** - `e4a8944` (feat)

_TDD task: RED committed failing tests, GREEN committed passing implementation_

## Files Created/Modified
- `src/lineaf/api/__init__.py` - Empty package init
- `src/lineaf/api/prices.py` - Price endpoints: current, history, index, Excel export
- `src/lineaf/api/products.py` - Product change detection (new/removed)
- `src/lineaf/api/runs.py` - Scrape run log and freshness endpoints
- `src/lineaf/main.py` - Router registration with /api prefix (also includes scheduler lifespan from linter)
- `pyproject.toml` - Added httpx, streamlit, apscheduler, plotly, requests dependencies
- `tests/test_api.py` - 8 test cases covering all endpoints with SQLite in-memory DB

## Decisions Made
- Used max(PriceSnapshot.id) subquery instead of max(scraped_at) for latest snapshot per product -- avoids ties and is deterministic
- StaticPool for SQLite in-memory test DB ensures all sessions share one connection (otherwise each gets a fresh empty DB)
- Naive datetime comparison fix: when SQLite strips timezone info, explicitly add UTC before comparing with aware cutoff datetime

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed naive/aware datetime comparison in freshness endpoint**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** SQLite stores datetimes without timezone info; comparing naive finished_at with timezone-aware stale_cutoff raised TypeError
- **Fix:** Added `if finished.tzinfo is None: finished = finished.replace(tzinfo=timezone.utc)` guard
- **Files modified:** src/lineaf/api/runs.py
- **Verification:** test_freshness_data passes
- **Committed in:** e4a8944 (part of GREEN commit)

**2. [Rule 3 - Blocking] Fixed SQLite in-memory StaticPool for test isolation**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** Default connection pool created separate connections for in-memory SQLite, each with empty DB (no tables)
- **Fix:** Added `poolclass=StaticPool` and `connect_args={"check_same_thread": False}` to test engine
- **Files modified:** tests/test_api.py
- **Verification:** All 8 tests pass
- **Committed in:** e4a8944 (part of GREEN commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking)
**Impact on plan:** Both fixes necessary for correct test execution. No scope creep.

## Issues Encountered
- Linter applied content from other plans (scheduler lifespan in main.py, /scrape endpoint in runs.py) -- kept these additions as they reference existing modules and don't conflict with this plan's endpoints.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 7 API endpoints ready for Streamlit dashboard consumption (Plan 03-02)
- Scheduler integration already wired into main.py lifespan
- Full test suite green (85 passed, 4 skipped)

## Self-Check: PASSED

All created files verified present. Both commit hashes (f68f410, e4a8944) confirmed in git log.

---
*Phase: 03-dashboard*
*Completed: 2026-03-15*
