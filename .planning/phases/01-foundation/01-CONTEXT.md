# Phase 1: Foundation - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Project scaffold, PostgreSQL schema, and dev environment. The database schema is the contract that scrapers (Phase 2) and dashboard (Phase 3) depend on. This phase delivers a working local environment with all three tables (products, price_snapshots, scrape_runs) ready for data.

</domain>

<decisions>
## Implementation Decisions

### Schema Design
- Claude's discretion on table structure — user trusts standard patterns
- Fields that may be missing on some sites should accept NULL — not all 3 competitors will have every field (e.g., weight, cover material)
- Field names should be normalized (unified naming across sites) even though source sites name things differently
- Firmness/height/filler/cover/weight stored as TEXT — values differ across sites, no reliable enum

### Dev Environment
- Claude's discretion on Docker vs local PostgreSQL setup
- Claude's discretion on dependency management (uv/pip/poetry)

### Migrations
- Claude's discretion on Alembic configuration
- No seed data needed from Excel in this phase — that's Phase 2 territory

### Claude's Discretion
User expressed full trust in standard implementation patterns for Phase 1. All infrastructure decisions (Docker setup, project structure, Alembic config, SQLAlchemy models) are at Claude's discretion.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `askona_160x200_full2705.xlsx` — reference for expected field names and data structure (not to be imported, but useful for schema design validation)

### Established Patterns
- No existing code — greenfield project

### Integration Points
- Schema must support the scraper pipeline (Phase 2): UPSERT products, INSERT price_snapshots, new/removed detection via is_active
- Schema must support dashboard queries (Phase 3): filtering by competitor, price history timeseries, freshness indicator

</code_context>

<specifics>
## Specific Ideas

- User previously collected Askona data manually — the Excel file shows the expected data structure
- Data fields may be named differently across sites or be missing entirely — schema should handle NULLs gracefully
- User emphasized that field normalization across sites is important for Phase 2

</specifics>

<deferred>
## Deferred Ideas

- Site structure research (askona.ru, ormatek.ru, sonum.ru) — belongs in Phase 2 research
- Handling missing/different field names across sites — Phase 2 spider implementation

</deferred>

---

*Phase: 01-foundation*
*Context gathered: 2026-03-14*
