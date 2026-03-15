---
phase: 3
slug: dashboard
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-15
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/test_api.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_api.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | DASH-01 | unit | `uv run pytest tests/test_api.py::test_get_prices -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | DASH-02 | unit | `uv run pytest tests/test_api.py::test_get_price_history -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | DASH-03 | unit | `uv run pytest tests/test_api.py::test_export_excel -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | DASH-04 | unit | `uv run pytest tests/test_api.py::test_price_index -x` | ❌ W0 | ⬜ pending |
| 03-01-05 | 01 | 1 | DASH-05 | unit | `uv run pytest tests/test_api.py::test_freshness_data -x` | ❌ W0 | ⬜ pending |
| 03-01-06 | 01 | 1 | DASH-06 | unit | `uv run pytest tests/test_api.py::test_product_changes -x` | ❌ W0 | ⬜ pending |
| 03-03-01 | 03 | 2 | SCHD-01 | unit | `uv run pytest tests/test_scheduler.py::test_cron_trigger -x` | ❌ W0 | ⬜ pending |
| 03-01-07 | 01 | 1 | SCHD-02 | unit | `uv run pytest tests/test_api.py::test_get_runs -x` | ❌ W0 | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tests/test_api.py` — FastAPI TestClient tests for all DASH requirements
- [ ] `tests/test_scheduler.py` — APScheduler job registration test
- [ ] `httpx` dev dependency for FastAPI TestClient

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Streamlit renders correctly | DASH-01..06 | Visual UI | Open browser, verify tables/charts/export |
| Freshness indicator turns red | DASH-05 | Time-dependent | Wait >8 days or mock date |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
