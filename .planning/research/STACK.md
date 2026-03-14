# Technology Stack

**Project:** Lineaf Price Tracker
**Researched:** 2026-03-14
**Overall confidence:** HIGH (all versions verified against PyPI, primary sources consulted)

---

## Recommended Stack

### Scraping Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Playwright (Python) | 1.58.0 | Headless browser automation | Askona, Ormatek, Sonum are JavaScript-heavy SPAs. Static HTML parsers (requests + BeautifulSoup) will not work — product listings are rendered client-side. Playwright executes real browser JS, handles dynamic loading, and supports async. |
| Camoufox | 0.4.11 | Anti-bot evasion layer | Drop-in Playwright-compatible wrapper built on a patched Firefox binary. Spoofs fingerprints at the C++ level (not JS injection), making headless detection by Cloudflare / DataDome significantly harder. Source: [ScrapingBee guide](https://www.scrapingbee.com/blog/how-to-scrape-with-camoufox-to-bypass-antibot-technology/). |

**Why not Scrapy:** Scrapy is an excellent HTML crawler but has no native JS execution. You would need `scrapy-playwright` as a plugin, adding complexity. For 3 sites with weekly runs, a pure Playwright script is simpler to maintain, debug, and extend. Scrapy's crawl-at-scale advantages are irrelevant for this use case.

**Why not Selenium:** Playwright is strictly faster (parallel async context manager), has a cleaner Python API, and is better maintained. Selenium's `webdriver.WebDriver` attribute is trivially detected by anti-bot systems even without stealth patches.

**Camoufox status note (LOW confidence on long-term maintenance):** The primary maintainer (@daijro) was hospitalized in March 2025. Active development has been picked up by @coryking and CloverLabsAI forks. The library is functional and widely used as of early 2026 but may lag behind on browser version updates. Evaluate `playwright-stealth` as a fallback if Camoufox diverges from compatibility. Source: [GitHub](https://github.com/daijro/camoufox).

---

### Database Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | 16+ | Primary data store | Relational model is a natural fit for structured product data with immutable price-history rows. Native JSON columns available for flexible spec storage. Confirmed in project constraints. |
| SQLAlchemy | 2.0.48 | Python ORM | Industry standard. Version 2.0 adds clean async support, modern type annotations, and breaks from 1.x legacy patterns cleanly. Declarative mapping keeps schema definition co-located with model code. Source: [PyPI](https://pypi.org/project/SQLAlchemy/). |
| Alembic | 1.18.4 | Schema migrations | The official SQLAlchemy migration tool. Autogenerate detects model changes and creates migration scripts. Essential for schema evolution without manual SQL. Source: [PyPI](https://pypi.org/project/alembic/). |
| psycopg (v3) | 3.3.3 | PostgreSQL driver | psycopg3 is 3-4x faster than psycopg2 for query throughput and ~4x more memory-efficient. Modern async API. SQLAlchemy 2.0 supports it natively. Use `psycopg[binary]` for pre-compiled binary. Source: [psycopg.org](https://www.psycopg.org/), [Tiger Data benchmark](https://www.tigerdata.com/blog/psycopg2-vs-psycopg3-performance-benchmark). |

**Why not psycopg2:** No new features planned; psycopg3 is the successor. The only reason to choose psycopg2 would be an environment that cannot compile psycopg3 binary wheels — not a concern on modern Linux VMs.

**Why not SQLite:** Weekly batch writes are fine with SQLite, but multi-user dashboard reads (several team members concurrently hitting the dashboard) are better served by PostgreSQL's connection handling and locking model.

---

### Scheduling Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| APScheduler | 3.11.2 | Weekly cron-style job scheduling | Lightweight, in-process scheduler. No message broker required. Perfect for "run scraper every Monday at 8:00" with a single cron expression. Source: [PyPI](https://pypi.org/project/apscheduler/). |

**Why not Celery + Redis:** Celery is designed for distributed task queues across multiple workers. This project needs one job, once a week, on one machine. Celery would require maintaining a Redis/RabbitMQ broker, a worker process, and a beat scheduler process — 3x the operational surface for no benefit.

**Alternative considered — system cron:** A plain Linux crontab entry invoking `python run_scraper.py` is equally valid and has zero Python dependencies. Prefer APScheduler when running inside a FastAPI app (can trigger scrapes via API endpoint or on schedule). If the scraper is a standalone script, system cron is simpler.

---

### API Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | ≥0.115 | REST API serving dashboard data | Confirmed in project constraints. Async-native, automatic OpenAPI docs, Pydantic validation. Serves JSON to the Streamlit frontend. |
| pydantic-settings | 2.13.1 | Configuration management | FastAPI-idiomatic way to load settings from `.env` files with type validation. Replaces plain `python-dotenv` for structured config. Source: [FastAPI docs](https://fastapi.tiangolo.com/advanced/settings/). |
| uvicorn | ≥0.32 | ASGI server | Standard server for FastAPI in both dev and production. |

---

### Dashboard Layer

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Streamlit | 1.55.0 | Internal team dashboard | Pure-Python dashboards with near-zero frontend code. For a small internal team (several people), Streamlit's time-to-dashboard is days, not weeks. Interactive price charts, competitor comparison tables, and filter widgets can all be built without JavaScript. Source: [PyPI](https://pypi.org/project/streamlit/). |
| Plotly (via Streamlit) | bundled | Price history charts | `st.plotly_chart()` renders interactive Plotly figures. Necessary for hover-to-see-price on historical line charts. |
| pandas | 3.0.1 | Data manipulation for display | Streamlit renders `pd.DataFrame` natively with `st.dataframe()`. Used for pivot tables and aggregation before display. Source: [PyPI](https://pypi.org/project/pandas/). |

**Why not Plotly Dash:** Dash is the right choice when you need complex callbacks, custom CSS layouts, or enterprise auth. For this project — a small team, internal tool, read-mostly dashboard — Streamlit's simpler model ships faster and is easier for non-frontend developers to maintain. Multiple 2025 comparisons converge on this recommendation for small teams. Source: [Squadbase 2025](https://www.squadbase.dev/en/blog/streamlit-vs-dash-in-2025-comparing-data-app-frameworks).

**Why not a React + FastAPI SPA:** Doubles the tech surface. Team would need to maintain a JS build pipeline alongside Python. Streamlit runs entirely in Python, reads from the same PostgreSQL database the scraper writes to, and requires no separate frontend deployment.

---

### Dev Tooling

| Tool | Version | Purpose | Why |
|------|---------|---------|-----|
| uv | latest | Package + virtualenv management | Replaces pip + virtualenv. Faster resolution, lockfile support (`uv.lock`), PEP 621 compliant. Recommended for new Python projects in 2025+. |
| python-dotenv | ≥1.0 | `.env` file loading in dev | Used by pydantic-settings under the hood; also useful for standalone scraper scripts. |
| pytest | ≥8.0 | Testing | Standard Python test runner. |
| pytest-playwright | ≥0.7 | Playwright test fixtures | Simplifies browser context setup in tests. |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Browser automation | Playwright + Camoufox | Scrapy + scrapy-playwright | More moving parts, Scrapy's middleware system adds overhead for 3-site use case |
| Browser automation | Playwright + Camoufox | Selenium + undetected-chromedriver | Slower, older API, worse async support |
| Scheduling | APScheduler | Celery + Redis | Requires broker infrastructure; overkill for weekly single-machine job |
| Scheduling | APScheduler | System cron | Valid alternative; prefer APScheduler if scraper integrates with FastAPI |
| Dashboard | Streamlit | Plotly Dash | Faster to build for small internal team; Dash better for complex interactivity |
| Dashboard | Streamlit | Grafana + TimescaleDB | Requires separate Grafana setup; overkill when backend is already Python/PostgreSQL |
| ORM | SQLAlchemy 2.x | Tortoise-ORM / encode/databases | SQLAlchemy has larger ecosystem, better Alembic integration, more community resources |
| DB driver | psycopg3 | psycopg2 | psycopg2 is legacy-stable but no new features; psycopg3 is the maintained successor |

---

## Installation

```bash
# Create and activate virtualenv (using uv)
uv venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows

# Scraping
uv pip install playwright camoufox

# Install browser binaries
playwright install chromium   # if using vanilla Playwright fallback
python -m camoufox fetch      # downloads the patched Firefox binary

# Database
uv pip install sqlalchemy alembic "psycopg[binary]"

# API
uv pip install fastapi uvicorn pydantic-settings python-dotenv

# Dashboard
uv pip install streamlit plotly pandas

# Scheduling
uv pip install apscheduler

# Dev
uv pip install pytest pytest-playwright
```

---

## Architecture Notes

The stack divides into three independently runnable processes:

1. **Scraper process** — Playwright/Camoufox script invoked by APScheduler (or cron). Writes to PostgreSQL.
2. **FastAPI process** — Serves `/api/prices`, `/api/products`, `/api/competitors` endpoints. Reads from PostgreSQL.
3. **Streamlit process** — Calls FastAPI (or queries PostgreSQL directly for simplicity in early iterations). Renders dashboard.

For a single-VM deployment, all three run as `systemd` services or `docker-compose` containers sharing a network. Streamlit can query PostgreSQL directly (skipping FastAPI) in v1 to minimize moving parts — FastAPI becomes valuable when you add auth, webhooks, or external API consumers later.

---

## Sources

- [playwright PyPI](https://pypi.org/project/playwright/) — version 1.58.0 confirmed
- [Camoufox GitHub](https://github.com/daijro/camoufox) — anti-bot Firefox fork
- [ScrapingBee: Camoufox guide](https://www.scrapingbee.com/blog/how-to-scrape-with-camoufox-to-bypass-antibot-technology/)
- [SQLAlchemy PyPI](https://pypi.org/project/SQLAlchemy/) — version 2.0.48 confirmed
- [Alembic PyPI](https://pypi.org/project/alembic/) — version 1.18.4 confirmed
- [psycopg PyPI](https://pypi.org/project/psycopg/) — version 3.3.3 confirmed
- [Tiger Data: psycopg2 vs psycopg3 benchmark](https://www.tigerdata.com/blog/psycopg2-vs-psycopg3-performance-benchmark)
- [APScheduler PyPI](https://pypi.org/project/apscheduler/) — version 3.11.2 confirmed
- [Streamlit PyPI](https://pypi.org/project/streamlit/) — version 1.55.0 confirmed
- [pandas PyPI](https://pypi.org/project/pandas/) — version 3.0.1 confirmed
- [pydantic-settings PyPI](https://pypi.org/project/pydantic-settings/) — version 2.13.1 confirmed
- [FastAPI settings docs](https://fastapi.tiangolo.com/advanced/settings/)
- [Squadbase: Streamlit vs Dash 2025](https://www.squadbase.dev/en/blog/streamlit-vs-dash-in-2025-comparing-data-app-frameworks)
- [Brightdata: Scrapy vs Playwright](https://brightdata.com/blog/web-data/scrapy-vs-playwright)
- [Leapcell: APScheduler vs Celery Beat](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-vs-celery-beat)
