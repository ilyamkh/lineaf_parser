---
phase: 2
slug: scrapers
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (already installed) |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` |
| **Quick run command** | `uv run pytest tests/test_pipeline.py -x` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds (unit), ~60 seconds (with integration) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_pipeline.py -x` (unit tests only)
- **After every plan wave:** Run `uv run pytest tests/ -v -m "not integration"`
- **Before `/gsd:verify-work`:** Full suite including integration tests
- **Max feedback latency:** 10 seconds (unit), 60 seconds (integration)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | SCRP-01 | integration | `uv run pytest tests/test_scrapers.py::test_askona_catalog_urls -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | SCRP-02 | integration | `uv run pytest tests/test_scrapers.py::test_ormatek_catalog_urls -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | SCRP-03 | integration | `uv run pytest tests/test_scrapers.py::test_sonum_catalog_urls -x` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 1 | SCRP-04 | unit | `uv run pytest tests/test_pipeline.py::test_product_fields_schema -x` | ❌ W0 | ⬜ pending |
| 02-04-02 | 04 | 1 | SCRP-05 | smoke | `uv run pytest tests/test_scrapers.py::test_camoufox_launches -x` | ❌ W0 | ⬜ pending |
| 02-04-03 | 04 | 1 | SCRP-06 | unit | `uv run pytest tests/test_pipeline.py::test_new_product_detection -x` | ❌ W0 | ⬜ pending |
| 02-04-04 | 04 | 1 | SCRP-07 | unit | `uv run pytest tests/test_pipeline.py::test_removed_product_detection -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_scrapers.py` — integration tests for SCRP-01..03, SCRP-05 (requires Camoufox)
- [ ] `tests/test_pipeline.py` — unit tests for SCRP-04, SCRP-06, SCRP-07
- [ ] Camoufox install: `uv add camoufox && python -m camoufox fetch`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| All 160×200 mattresses scraped (no pagination truncation) | SCRP-01..03 | Count varies over time | Compare scraped count with manual site count |
| Correct field mapping across sites | SCRP-04 | Field names differ per site | Spot-check 3 products per site against website |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
