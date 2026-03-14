---
phase: 02-scrapers
plan: 01
subsystem: scrapers
tags: [camoufox, playwright, upsert, sqlalchemy, pipeline, price-parsing]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: Product, PriceSnapshot, ScrapeRun models, database.py SessionLocal
provides:
  - BaseScraper abstract class with Camoufox browser context and retry logic
  - Item pipeline (upsert_product, insert_price_snapshot, mark_removed_products)
  - parse_price utility for Russian price formats
  - validate_product minimum field checker
  - run_scrapers.py CLI entry point for sequential execution
affects: [02-scrapers plans 02-04, all site spider implementations]

# Tech tracking
tech-stack:
  added: [camoufox, playwright (bundled)]
  patterns: [dialect-aware UPSERT (PostgreSQL atomic / SQLite fallback), 0-result guard for deactivation, TDD for pipeline logic]

key-files:
  created:
    - src/lineaf/scrapers/__init__.py
    - src/lineaf/scrapers/base.py
    - src/lineaf/scrapers/pipeline.py
    - src/lineaf/scrapers/utils.py
    - src/lineaf/run_scrapers.py
    - tests/test_pipeline.py
  modified:
    - pyproject.toml
    - uv.lock

key-decisions:
  - "Dialect-aware UPSERT: PostgreSQL uses atomic ON CONFLICT DO UPDATE, SQLite uses SELECT-then-INSERT/UPDATE fallback for test compatibility"
  - "Dynamic spider import in run_scrapers.py via registry dict to avoid circular imports"

patterns-established:
  - "BaseScraper subclass pattern: implement collect_product_urls + extract_product abstract methods"
  - "Pipeline flow: validate_product -> upsert_product -> insert_price_snapshot -> mark_removed_products"
  - "parse_price: strip non-digit chars, comma->dot, Decimal conversion for Russian price formats"

requirements-completed: [SCRP-04, SCRP-05, SCRP-06, SCRP-07]

# Metrics
duration: 5min
completed: 2026-03-14
---

# Phase 2 Plan 1: Scraper Foundation Summary

**Camoufox BaseScraper with async retry, item pipeline (UPSERT + change detection), parse_price utility, and 19 passing unit tests on SQLite**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-14T15:36:06Z
- **Completed:** 2026-03-14T15:41:13Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Item pipeline with dialect-aware UPSERT (PostgreSQL atomic / SQLite fallback), price snapshot insertion, and removed-product detection with 0-result safety guard
- parse_price handles all Russian price formats (spaces, currency symbols, comma decimals) and validate_product enforces name + price minimum
- BaseScraper abstract class with AsyncCamoufox headless browser, 3-attempt retry with 30-60s backoff, 2-5s random delay, and full ScrapeRun lifecycle management
- CLI entry point (run_scrapers.py) with argparse for selective or full site execution
- 19 unit tests covering all pipeline and utility behaviors pass on SQLite in-memory

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for pipeline** - `73530ce` (test)
2. **Task 1 (GREEN): Pipeline and utils implementation** - `3f8a30d` (feat)
3. **Task 2: BaseScraper + Camoufox + entry point** - `0b9e931` (feat)

_TDD task 1 had RED and GREEN commits; no REFACTOR needed._

## Files Created/Modified
- `src/lineaf/scrapers/__init__.py` - Package init (empty)
- `src/lineaf/scrapers/base.py` - BaseScraper: Camoufox context, retry, delay, ScrapeRun lifecycle, abstract methods
- `src/lineaf/scrapers/pipeline.py` - upsert_product, insert_price_snapshot, mark_removed_products
- `src/lineaf/scrapers/utils.py` - parse_price, validate_product
- `src/lineaf/run_scrapers.py` - CLI entry point with argparse and sequential execution
- `tests/test_pipeline.py` - 19 unit tests for pipeline and utility functions
- `pyproject.toml` - Added camoufox dependency
- `uv.lock` - Updated lockfile

## Decisions Made
- Dialect-aware UPSERT strategy: PostgreSQL gets atomic `INSERT ... ON CONFLICT DO UPDATE`, SQLite gets SELECT-then-INSERT/UPDATE fallback. This allows unit tests to run without PostgreSQL.
- Dynamic spider import via registry dict in run_scrapers.py to prevent circular imports and allow spider modules to not yet exist.
- Did NOT use `geoip=True` in AsyncCamoufox per plan note (avoids heavy optional dependency).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed parse_price trailing dot from "rub." suffix**
- **Found during:** Task 1 (GREEN phase)
- **Issue:** "12 345,67 rub." became "12345.67." after regex cleaning -- trailing dot from Cyrillic "rub." made Decimal parse fail
- **Fix:** Added `.strip(".")` after regex cleaning to remove leading/trailing dots
- **Files modified:** src/lineaf/scrapers/utils.py
- **Verification:** test_price_with_comma_decimal passes
- **Committed in:** 3f8a30d (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix for Russian price parsing correctness. No scope creep.

## Issues Encountered
- Cyrillic path in project directory causes `.pth` file to not work with `uv run python -c` (known issue from Phase 1). All imports verified via `PYTHONPATH=src` workaround. Tests work normally through pytest.

## User Setup Required
None - camoufox browser binary downloaded automatically via `python -m camoufox fetch`.

## Next Phase Readiness
- BaseScraper and pipeline ready for site-specific spider subclasses (askona, ormatek, sonum)
- All abstract methods defined: `collect_product_urls` and `extract_product`
- Pipeline tested and proven: UPSERT, price snapshots, change detection all working

## Self-Check: PASSED

All 6 created files exist. All 3 task commits verified (73530ce, 3f8a30d, 0b9e931).

---
*Phase: 02-scrapers*
*Completed: 2026-03-14*
