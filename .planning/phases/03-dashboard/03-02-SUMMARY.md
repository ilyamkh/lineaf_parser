---
phase: 03-dashboard
plan: 02
subsystem: scheduler
tags: [apscheduler, cron, fastapi-lifespan, background-thread]

requires:
  - phase: 02-scrapers
    provides: "run_scrapers.main() entry point for sequential scraping"
provides:
  - "APScheduler BackgroundScheduler with Monday 03:00 Moscow cron job"
  - "FastAPI lifespan context manager for scheduler lifecycle"
  - "POST /api/scrape endpoint for manual trigger via daemon thread"
affects: [03-dashboard]

tech-stack:
  added: [apscheduler, tzlocal]
  patterns: [fastapi-lifespan, daemon-thread-background-task]

key-files:
  created: [src/lineaf/scheduler.py, tests/test_scheduler.py]
  modified: [src/lineaf/main.py, src/lineaf/api/runs.py, pyproject.toml, uv.lock]

key-decisions:
  - "BackgroundScheduler (not AsyncIOScheduler) to avoid asyncio.run() conflicts with scrapers"
  - "Daemon thread for POST /scrape instead of FastAPI BackgroundTasks to avoid blocking worker pool"

patterns-established:
  - "Lifespan pattern: asynccontextmanager for startup/shutdown hooks in main.py"
  - "Manual trigger pattern: daemon thread for long-running scraper invocations"

requirements-completed: [SCHD-01, SCHD-02]

duration: 2min
completed: 2026-03-15
---

# Phase 3 Plan 2: Scheduler Summary

**APScheduler BackgroundScheduler with Monday 03:00 Moscow time cron job, FastAPI lifespan lifecycle, and POST /api/scrape daemon-thread trigger**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-15T05:16:32Z
- **Completed:** 2026-03-15T05:18:44Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- APScheduler BackgroundScheduler registered with weekly Monday 03:00 Europe/Moscow cron trigger
- FastAPI lifespan starts/stops scheduler cleanly on app lifecycle
- POST /api/scrape starts scrapers in daemon thread, returns immediately
- TDD test suite validates job registration, trigger config, and start/stop cycle

## Task Commits

Each task was committed atomically:

1. **Task 1: Create scheduler module and tests (TDD)** - `9737700` (feat)
2. **Task 2: Wire scheduler lifespan and POST /api/scrape** - `43970b5` (feat)

## Files Created/Modified
- `src/lineaf/scheduler.py` - APScheduler setup with start/stop functions and cron job registration
- `tests/test_scheduler.py` - Tests for cron trigger fields and scheduler lifecycle
- `src/lineaf/main.py` - Added lifespan context manager, all API router includes
- `src/lineaf/api/runs.py` - Added POST /scrape endpoint with daemon thread
- `pyproject.toml` - Added apscheduler dependency
- `uv.lock` - Updated lockfile

## Decisions Made
- Used BackgroundScheduler (not AsyncIOScheduler) because scrapers call asyncio.run() internally which conflicts with an already-running event loop
- Used daemon thread for POST /scrape instead of FastAPI BackgroundTasks to avoid blocking the ASGI worker thread pool during 10+ minute scraper runs

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added apscheduler dependency**
- **Found during:** Task 1 (scheduler module creation)
- **Issue:** apscheduler not in pyproject.toml dependencies
- **Fix:** Ran `uv add apscheduler` which also pulled in tzlocal
- **Files modified:** pyproject.toml, uv.lock
- **Verification:** Import succeeds, tests pass
- **Committed in:** 9737700 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Dependency installation required for functionality. No scope creep.

## Issues Encountered
- Plan 03-01 had already created stub API router files and updated main.py with include_router calls. Task 2 adapted by editing existing files rather than writing from scratch.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Scheduler and manual scrape trigger ready
- Plan 03-01 API endpoints (when implemented) will be automatically included via existing router registrations
- Plan 03-03 Streamlit dashboard can call POST /api/scrape for manual triggers

## Self-Check: PASSED

All files exist. All commits verified.

---
*Phase: 03-dashboard*
*Completed: 2026-03-15*
