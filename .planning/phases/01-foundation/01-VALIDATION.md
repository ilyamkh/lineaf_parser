---
phase: 1
slug: foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` — `[tool.pytest.ini_options]` — Wave 0 creates it |
| **Quick run command** | `uv run pytest tests/test_models.py -x` |
| **Full suite command** | `uv run pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_models.py -x`
- **After every plan wave:** Run `uv run pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | STOR-01 | unit | `uv run pytest tests/test_models.py::test_product_deduplication -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 1 | STOR-02 | unit | `uv run pytest tests/test_models.py::test_price_snapshot_decimal -x` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 1 | STOR-03 | unit | `uv run pytest tests/test_models.py::test_scrape_run_insert -x` | ❌ W0 | ⬜ pending |
| 01-01-04 | 01 | 1 | STOR-04 | unit | `uv run pytest tests/test_models.py::test_is_active_flag -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — engine fixture pointing at test DB, session fixture with rollback teardown
- [ ] `tests/test_models.py` — stubs for STOR-01 through STOR-04
- [ ] Framework install: `uv add --dev pytest` — no pytest detected yet (greenfield)
- [ ] Test DB URL: add `TEST_DATABASE_URL` to `.env.example`; conftest reads it or creates `lineaf_test` database

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `docker-compose up` starts PostgreSQL | STOR-01 | Container orchestration | Run `docker-compose up -d`, verify `docker ps` shows healthy postgres |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
