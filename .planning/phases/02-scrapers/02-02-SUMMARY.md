---
phase: 02-scrapers
plan: 02
subsystem: scrapers
tags: [askona, next-data-json, playwright, camoufox, decimal-prices]

# Dependency graph
requires:
  - phase: 02-scrapers/01
    provides: "BaseScraper base class, pipeline (upsert/snapshot), utils (parse_price/validate), run_scrapers registry"
provides:
  - "AskonaScraper class with catalog pagination and __NEXT_DATA__ JSON extraction"
  - "Standalone parse functions (parse_askona_catalog_json, parse_askona_product_json) for testing"
  - "Unit test suite for Askona JSON extraction logic"
affects: [02-scrapers/03, 02-scrapers/04, 03-dashboard]

# Tech tracking
tech-stack:
  added: []
  patterns: ["__NEXT_DATA__ JSON extraction via regex + json.loads", "Standalone parse functions separated from async page methods for testability"]

key-files:
  created:
    - src/lineaf/scrapers/askona.py
    - tests/test_scrapers.py
  modified: []

key-decisions:
  - "Extracted JSON parsing into standalone functions (parse_askona_catalog_json, parse_askona_product_json) for unit testing without browser"
  - "Zero oldPrice treated as None (no discount) rather than Decimal(0)"

patterns-established:
  - "Site scraper pattern: standalone parse functions + async class methods that call them"
  - "Test fixture pattern: sample JSON dicts mimicking __NEXT_DATA__ structure"

requirements-completed: [SCRP-01, SCRP-04, SCRP-05]

# Metrics
duration: 3min
completed: 2026-03-14
---

# Phase 02 Plan 02: Askona Spider Summary

**AskonaScraper with __NEXT_DATA__ JSON extraction, Russian field mapping for 8 attributes + 2 prices, and 9 unit tests**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-14T15:44:17Z
- **Completed:** 2026-03-14T15:46:47Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- AskonaScraper subclasses BaseScraper with catalog pagination via ?page=N
- All 8 attribute fields + 2 price fields mapped from Russian characteristic names
- URL extraction preserves SELECTED_HASH_SIZE parameter for correct 160x200 pricing
- 9 unit tests pass for JSON extraction without needing a browser
- Integration test stubs exist for manual live Camoufox verification

## Task Commits

Each task was committed atomically:

1. **Task 1: AskonaScraper with JSON extraction and field mapping** - `4c8f789` (feat)
2. **Task 2: Unit tests for Askona JSON extraction logic** - `613f66a` (test)

## Files Created/Modified
- `src/lineaf/scrapers/askona.py` - AskonaScraper class with catalog pagination and product extraction via __NEXT_DATA__ JSON
- `tests/test_scrapers.py` - 9 unit tests for catalog URL parsing, product field mapping, price types, and edge cases; 2 integration test stubs

## Decisions Made
- Extracted JSON parsing into standalone functions for testability without browser dependencies
- Zero oldPrice treated as None rather than Decimal(0) to match pipeline's validate_product expectations
- Alternative Russian field names (e.g., "Съемный чехол" for cover_material) supported via ordered key lists

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- AskonaScraper ready for live testing with Camoufox browser
- Pattern established for Sonum (02-03) and Ormatek (02-04) scrapers: standalone parse functions + async class
- run_scrapers.py already has askona registered in SPIDER_REGISTRY

---
*Phase: 02-scrapers*
*Completed: 2026-03-14*
