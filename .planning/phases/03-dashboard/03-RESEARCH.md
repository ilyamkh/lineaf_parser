# Phase 3: Dashboard & Scheduling - Research

**Researched:** 2026-03-15
**Domain:** Streamlit dashboard + FastAPI backend + APScheduler cron
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Language:** All UI labels, headers, and buttons in Russian
- **Charts:** Three chart types required:
  1. Динамика товара — line chart of a specific product's price over weeks
  2. Сравнение конкурентов — average price per competitor over time
  3. Распределение цен — histogram or box-plot of prices per competitor
- **Price field on charts:** price_sale (after discount) — the real purchase price
- **Scheduling:** Weekly auto-scrape + manual "Запустить парсинг" button in dashboard
- **Stack:** Streamlit for dashboard, FastAPI for API, APScheduler embedded in FastAPI process
- **Freshness indicator:** Red if data >8 days old (already in requirements)

### Claude's Discretion
- Dashboard framework details (Streamlit layout, tab vs single-page, components)
- FastAPI endpoint structure
- APScheduler configuration details
- Chart library (Plotly recommended) and interactivity level
- Whether to include KPI overview panel at top
- Error handling beyond the red freshness indicator

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DASH-01 | Дашборд показывает таблицу текущих цен по конкурентам с фильтрацией | st.dataframe + sidebar multiselect; /api/prices endpoint with site/product filters |
| DASH-02 | Дашборд показывает графики динамики цен по выбранным товарам/конкурентам | px.line (Динамика), px.line grouped (Сравнение), px.box or px.histogram (Распределение) via /api/prices with history |
| DASH-03 | Дашборд позволяет экспортировать данные в Excel/CSV | st.download_button with BytesIO + pandas to_excel(); /api/export endpoint |
| DASH-04 | Дашборд показывает ценовой индекс (средняя цена категории по конкурентам) | KPI metric cards via st.metric; SQL avg(price_sale) group by source_site |
| DASH-05 | Дашборд показывает индикатор свежести данных (когда последний раз собирались) | Query latest finished_at from scrape_runs per site; red color if >8 days |
| DASH-06 | Дашборд показывает список новых и удалённых позиций | Query scrape_runs for latest run_id, join products with products_new/products_removed counts; or query products by first_seen_at/is_active transitions |
| SCHD-01 | Парсер запускается автоматически раз в неделю по расписанию | APScheduler BackgroundScheduler with CronTrigger(day_of_week='mon', hour=3) started in FastAPI lifespan |
| SCHD-02 | Лог успешных/неуспешных запусков доступен в дашборде | /api/runs endpoint returning scrape_runs rows; displayed as st.dataframe in dashboard |
</phase_requirements>

---

## Summary

Phase 3 builds the read-side of the system: a Streamlit dashboard backed by a FastAPI API layer, with APScheduler running weekly scrapes automatically. All three components run in a single Python process via FastAPI lifespan. The existing codebase already has `main.py` (a FastAPI stub), `database.py` with `get_db()` ready for dependency injection, and `run_scrapers.py` callable as the scheduler job target.

The key architectural decision is **Streamlit calling FastAPI via HTTP** rather than accessing the database directly. This separates concerns and makes the API independently usable (e.g., for future automation). The Streamlit app runs as a separate process (port 8501) while FastAPI runs on port 8000; both can be orchestrated with Docker Compose or a simple shell script. APScheduler's `BackgroundScheduler` is embedded inside the FastAPI process (started/stopped in `lifespan`), which calls `run_scrapers.main()` in a thread.

The three libraries needed (Streamlit 1.55.0, APScheduler 3.11.2, Plotly 6.x) are not yet installed and must be added to `pyproject.toml`.

**Primary recommendation:** Tab layout with four tabs (Цены, Графики, Изменения, Логи) + sidebar filters + KPI metrics row. Use Plotly Express for all charts. APScheduler BackgroundScheduler with CronTrigger Monday 03:00.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| streamlit | 1.55.0 | Dashboard UI framework | Pure Python, no JS build pipeline, ships fast |
| fastapi | 0.135.1 | REST API (already installed) | Already in project, async, auto-docs |
| apscheduler | 3.11.2 | Cron scheduling | Embedded in-process, no broker needed, stable |
| plotly | 6.x (latest) | Interactive charts | Best Streamlit integration; `st.plotly_chart` native; interactive hover |
| pandas | 3.0.1 | Data manipulation (already installed) | Already in project; to_excel, to_csv, filtering |
| openpyxl | 3.1.5 | Excel file writing (already installed) | Required by pandas to_excel |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx or requests | any | Streamlit calls FastAPI | Streamlit-to-FastAPI HTTP calls |
| uvicorn[standard] | 0.41.0 | ASGI server (already installed) | FastAPI runtime |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Plotly | Altair | Altair is declarative/elegant but Plotly has better Streamlit native integration and more chart types |
| Plotly | Matplotlib | Matplotlib is static; Plotly gives interactive hover for free |
| APScheduler 3.x | APScheduler 4.x | APScheduler 4 has different API (async-first); 3.x is stable, well-documented, simpler for this use case |
| Streamlit calls FastAPI | Streamlit directly queries DB | Direct DB is simpler but couples dashboard to DB schema; FastAPI adds a reusable API layer |

**Installation (to add to pyproject.toml):**
```bash
uv add streamlit apscheduler plotly requests
```

---

## Architecture Patterns

### Recommended Project Structure
```
src/lineaf/
├── main.py              # FastAPI app + APScheduler lifespan (expand existing stub)
├── api/
│   ├── __init__.py
│   ├── prices.py        # GET /api/prices, GET /api/export
│   ├── products.py      # GET /api/products
│   └── runs.py          # GET /api/runs, POST /api/scrape
├── dashboard/
│   ├── __init__.py
│   └── app.py           # Streamlit app entry point
├── scheduler.py         # APScheduler setup + job function
├── database.py          # existing — unchanged
├── config.py            # existing — unchanged
├── models/              # existing — unchanged
└── scrapers/            # existing — unchanged
```

### Pattern 1: FastAPI Lifespan + APScheduler
**What:** Start/stop BackgroundScheduler as part of FastAPI startup/shutdown
**When to use:** Single-machine deployment, no broker needed, weekly job

```python
# src/lineaf/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from lineaf.run_scrapers import main as run_scrapers_main

scheduler = BackgroundScheduler()

def start_scheduler():
    scheduler.add_job(
        run_scrapers_main,
        trigger=CronTrigger(day_of_week="mon", hour=3, minute=0),
        id="weekly_scrape",
        replace_existing=True,
    )
    scheduler.start()

def stop_scheduler():
    scheduler.shutdown(wait=False)
```

```python
# src/lineaf/main.py  (expand existing stub)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from lineaf.scheduler import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()

app = FastAPI(title="Lineaf Parser", lifespan=lifespan)

# Include routers
from lineaf.api import prices, products, runs
app.include_router(prices.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
```

### Pattern 2: FastAPI Endpoints for Dashboard Data
**What:** SQL queries via SQLAlchemy, returned as lists of Pydantic models
**When to use:** All dashboard data reads

```python
# src/lineaf/api/prices.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from lineaf.database import get_db
from lineaf.models import Product, PriceSnapshot
import pandas as pd

router = APIRouter()

@router.get("/prices")
def get_prices(
    site: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    q = (
        db.query(PriceSnapshot, Product)
        .join(Product)
        .filter(Product.is_active == True)
    )
    if site:
        q = q.filter(Product.source_site.in_(site))
    rows = q.all()
    # Return as list of dicts — FastAPI serializes via jsonable_encoder
    return [
        {
            "product_id": p.id,
            "name": p.name,
            "source_site": p.source_site,
            "price_sale": float(s.price_sale) if s.price_sale else None,
            "price_original": float(s.price_original) if s.price_original else None,
            "scraped_at": s.scraped_at.isoformat(),
        }
        for s, p in rows
    ]
```

**Critical:** `Decimal` fields from SQLAlchemy must be explicitly converted to `float()` or `str()` before returning — FastAPI's `jsonable_encoder` converts Decimal to float/int inconsistently depending on Pydantic version. Use explicit `float(value)` conversion.

### Pattern 3: Streamlit Tab Layout
**What:** Four tabs, sidebar for filters, KPI metrics row at top
**When to use:** Multiple logical sections of content

```python
# src/lineaf/dashboard/app.py
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from io import BytesIO

API_BASE = "http://localhost:8000/api"

st.set_page_config(page_title="Lineaf — Цены конкурентов", layout="wide")
st.title("Цены конкурентов")

# Sidebar filters
with st.sidebar:
    st.header("Фильтры")
    sites = st.multiselect(
        "Конкурент",
        options=["askona", "ormatek", "sonum"],
        default=["askona", "ormatek", "sonum"],
        format_func=lambda x: {"askona": "Аскона", "ormatek": "Орматек", "sonum": "Сонум"}[x],
    )

tab1, tab2, tab3, tab4 = st.tabs(["Цены", "Графики", "Изменения", "Логи"])

with tab1:
    # DASH-01: Filterable table
    # DASH-04: KPI metrics
    # DASH-03: Export button
    pass

with tab2:
    # DASH-02: Charts
    pass

with tab3:
    # DASH-06: New/removed products
    pass

with tab4:
    # SCHD-02: Run log
    pass
```

### Pattern 4: Manual Scrape Trigger
**What:** Button calls POST /api/scrape which runs scrapers in a background thread
**When to use:** "Запустить парсинг" button click

```python
# In Streamlit dashboard (tab4 or sidebar)
if st.button("Запустить парсинг"):
    with st.spinner("Запускаем парсер..."):
        resp = requests.post(f"{API_BASE}/scrape")
        if resp.status_code == 200:
            st.success("Парсинг запущен")
        else:
            st.error("Ошибка запуска")

# In FastAPI runs.py
import threading
from lineaf.run_scrapers import main as run_scrapers_main

@router.post("/scrape")
def trigger_scrape(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scrapers_main)
    return {"status": "started"}
```

**Note:** FastAPI `BackgroundTasks` is sufficient here — scraper runs in same process thread pool. The scraper already handles its own ScrapeRun logging. The response returns immediately (202-style) while scraping continues in background.

### Pattern 5: Excel Export
**What:** In-memory BytesIO buffer, `st.download_button`
**When to use:** DASH-03 Export requirement

```python
# In Streamlit
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Цены")
    buf.seek(0)
    return buf.read()

excel_bytes = to_excel_bytes(df_prices)
st.download_button(
    label="Экспорт в Excel",
    data=excel_bytes,
    file_name="lineaf_prices.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)
```

### Pattern 6: Freshness Indicator (DASH-05)
**What:** Query latest `finished_at` per site from scrape_runs; red if >8 days
**When to use:** Top of Цены tab

```python
# FastAPI: /api/runs?latest_per_site=true
# Returns: [{"site": "askona", "last_success": "2026-03-10T03:00:00", ...}]

# Streamlit: color-coded metric per site
from datetime import datetime, timezone, timedelta
STALE_THRESHOLD = timedelta(days=8)

for run in latest_runs:
    last = datetime.fromisoformat(run["last_success"]) if run.get("last_success") else None
    is_stale = (last is None) or (datetime.now(timezone.utc) - last > STALE_THRESHOLD)
    color = "red" if is_stale else "green"
    label = f":{color}[{site_names[run['site']]}]"
    value = last.strftime("%d.%m.%Y %H:%M") if last else "Нет данных"
    st.metric(label=label, value=value)
```

**Note:** `st.metric` with colored markdown in label is the pattern for colored KPI cards. `:{color}[text]` is Streamlit's colored text syntax.

### Anti-Patterns to Avoid
- **Streamlit querying DB directly:** Couples dashboard to DB schema; use FastAPI layer
- **Synchronous scraper call in HTTP handler:** Will block the request thread for minutes; always use `BackgroundTasks`
- **Storing Decimal without converting:** FastAPI's jsonable_encoder inconsistently handles Decimal; always cast to `float()` explicitly
- **APScheduler `AsyncIOScheduler` in this project:** The scrapers use `asyncio.run()` internally, which conflicts with an already-running event loop. Use `BackgroundScheduler` (runs in its own thread) instead
- **use_container_width=True in st.plotly_chart:** Deprecated in Streamlit 1.55. Use `width="stretch"` instead
- **Calling `scheduler.start()` outside lifespan:** If called at module import, starts a thread on every Uvicorn worker reload

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cron scheduling | Custom cron parser + threading.Timer | APScheduler CronTrigger | Handles timezone, missed jobs, job stores |
| Excel file generation | Manual XML/zip construction | pandas to_excel + openpyxl | Complex format, already available |
| Interactive charts | Matplotlib + mpld3 | Plotly Express | Interactive hover, zoom, legend toggle out-of-the-box |
| DataFrame UI with sort/search | Custom HTML table | st.dataframe | Built-in sorting, search, copy — free |
| Decimal JSON serialization | Custom JSONResponse subclass | Explicit float() cast at query boundary | Simpler, no custom encoder needed |

**Key insight:** Streamlit, Plotly, and APScheduler together cover 100% of the dashboard and scheduling requirements with zero custom UI code. The only custom logic is SQL queries and data shaping.

---

## Common Pitfalls

### Pitfall 1: APScheduler AsyncIOScheduler + asyncio.run() conflict
**What goes wrong:** `AsyncIOScheduler` runs jobs in the existing asyncio event loop. If a job calls `asyncio.run()` (which the scrapers do), it raises `RuntimeError: This event loop is already running`.
**Why it happens:** The scrapers use `asyncio.run(spider.run())` which cannot be nested inside an already-running loop.
**How to avoid:** Use `BackgroundScheduler` (thread-based). It runs the job in a separate thread where `asyncio.run()` works fine.
**Warning signs:** `RuntimeError: This event loop is already running` in scheduler logs.

### Pitfall 2: Streamlit re-runs on every interaction
**What goes wrong:** Every button click, widget change, or selectbox selection re-runs the entire Streamlit script from top to bottom, including expensive API calls.
**Why it happens:** Streamlit's execution model is "re-run the whole script on state change."
**How to avoid:** Use `@st.cache_data(ttl=60)` on functions that call the FastAPI API. The TTL means data refreshes at most once per minute, not on every widget interaction.
**Warning signs:** Dashboard feels slow; API logs show dozens of requests per second.

### Pitfall 3: Decimal serialization producing wrong JSON
**What goes wrong:** `price_sale` comes out as `"1234.56"` (string) or `1234` (truncated int) in the JSON response.
**Why it happens:** FastAPI's `jsonable_encoder` behavior with `Decimal` varies by Pydantic version. Pydantic v2 serializes Decimal as str; v1 as float. The project uses SQLAlchemy Decimal from NUMERIC(12,2).
**How to avoid:** Always cast at the query boundary: `float(snapshot.price_sale) if snapshot.price_sale is not None else None`.
**Warning signs:** Plotly charts show NaN values or prices displayed as strings in the table.

### Pitfall 4: BackgroundTasks blocks Uvicorn worker
**What goes wrong:** `POST /api/scrape` takes 10+ minutes (scrapers use Playwright). If `BackgroundTasks` is used, the Uvicorn worker's thread pool may be exhausted.
**Why it happens:** FastAPI `BackgroundTasks` runs in the same thread pool as request handlers. Long-running tasks can starve new requests.
**How to avoid:** Run scrapers via `threading.Thread(daemon=True, target=run_scrapers_main).start()`. This gives the scraper its own thread outside FastAPI's pool. Return 202 immediately.
**Warning signs:** New API requests time out while scraping is in progress.

### Pitfall 5: Multiple APScheduler starts on Uvicorn reload
**What goes wrong:** `scheduler.start()` is called multiple times — once per worker or on hot-reload — spawning duplicate scheduler threads with duplicate jobs running at the same time.
**Why it happens:** If `start_scheduler()` is called at module import level (not in lifespan), every Uvicorn reload triggers it again.
**How to avoid:** Only call `scheduler.start()` inside the `lifespan` async context manager. Use `replace_existing=True` when adding jobs as a safety net.
**Warning signs:** Scraper runs twice within seconds of each other; duplicate scrape_runs rows.

### Pitfall 6: st.download_button with BytesIO — forgot seek(0)
**What goes wrong:** Downloaded Excel/CSV file is 0 bytes or corrupted.
**Why it happens:** After writing to BytesIO, the stream cursor is at the end. Reading from end returns empty bytes.
**How to avoid:** Always call `buf.seek(0)` before reading or passing to `download_button`.

---

## Code Examples

### Chart 1: Динамика товара (product price history line chart)
```python
# Source: Plotly Express docs / Streamlit st.plotly_chart API
import plotly.express as px

# df_history: columns = [scraped_at (datetime), price_sale (float), name (str)]
fig = px.line(
    df_history,
    x="scraped_at",
    y="price_sale",
    color="name",
    labels={"scraped_at": "Дата", "price_sale": "Цена со скидкой (руб.)", "name": "Товар"},
    title="Динамика цены товара",
)
st.plotly_chart(fig, width="stretch")
```

### Chart 2: Сравнение конкурентов (avg price per competitor over time)
```python
# df_avg: columns = [scraped_at, source_site, avg_price_sale]
fig = px.line(
    df_avg,
    x="scraped_at",
    y="avg_price_sale",
    color="source_site",
    labels={"scraped_at": "Дата", "avg_price_sale": "Средняя цена (руб.)", "source_site": "Конкурент"},
    title="Средние цены по конкурентам",
)
st.plotly_chart(fig, width="stretch")
```

### Chart 3: Распределение цен (box plot per competitor)
```python
# df_prices: columns = [price_sale (float), source_site (str)]
fig = px.box(
    df_prices,
    x="source_site",
    y="price_sale",
    color="source_site",
    labels={"source_site": "Конкурент", "price_sale": "Цена со скидкой (руб.)"},
    title="Распределение цен по конкурентам",
)
st.plotly_chart(fig, width="stretch")
```

### KPI metrics (DASH-04 price index)
```python
# One st.metric per competitor
cols = st.columns(3)
for col, site_data in zip(cols, avg_prices_by_site):
    col.metric(
        label=site_data["site_label"],
        value=f"{site_data['avg_price']:,.0f} руб.",
    )
```

### APScheduler CronTrigger — Monday 3:00 AM
```python
# Source: APScheduler 3.x docs
from apscheduler.triggers.cron import CronTrigger

trigger = CronTrigger(day_of_week="mon", hour=3, minute=0, timezone="Europe/Moscow")
scheduler.add_job(run_scrapers_main, trigger=trigger, id="weekly_scrape", replace_existing=True)
```

### FastAPI /api/runs endpoint (SCHD-02)
```python
@router.get("/runs")
def get_runs(db: Session = Depends(get_db), limit: int = 50):
    runs = db.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "site": r.site,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "products_found": r.products_found,
            "products_new": r.products_new,
            "products_removed": r.products_removed,
            "error_message": r.error_message,
        }
        for r in runs
    ]
```

### DASH-06: New/removed products detection
```python
# Query: products that appeared in the latest scrape run (products_new)
# and products where is_active changed to False in latest run (products_removed)
# Simplest approach: query products ordered by first_seen_at desc for new,
# and is_active=False ordered by updated_at desc for removed

@router.get("/products/changes")
def get_product_changes(db: Session = Depends(get_db)):
    # Latest scrape run per site
    from sqlalchemy import func
    latest_run_ids = (
        db.query(func.max(ScrapeRun.id))
        .filter(ScrapeRun.status == "success")
        .group_by(ScrapeRun.site)
        .subquery()
    )
    # New products: appeared in latest runs (first_seen matches latest run time)
    # Removed: is_active=False updated recently
    new_products = (
        db.query(Product)
        .join(PriceSnapshot, Product.id == PriceSnapshot.product_id)
        .filter(PriceSnapshot.scrape_run_id.in_(latest_run_ids))
        .filter(Product.first_seen_at == Product.updated_at)  # first time seen
        .limit(50)
        .all()
    )
    removed_products = (
        db.query(Product)
        .filter(Product.is_active == False)
        .order_by(Product.updated_at.desc())
        .limit(50)
        .all()
    )
    return {
        "new": [{"name": p.name, "site": p.source_site} for p in new_products],
        "removed": [{"name": p.name, "site": p.source_site} for p in removed_products],
    }
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `use_container_width=True` in st.plotly_chart | `width="stretch"` | Streamlit 1.42+ | Old param deprecated, use new width param |
| APScheduler 4.x async-native | APScheduler 3.x (3.11.2) | 2024 | v4 is async-first, different API — stick to 3.x for simplicity |
| Streamlit single-page all sections | `st.tabs()` multi-tab layout | Streamlit 1.16+ | Tabs are now the standard for multi-section dashboards |
| Direct DB in Streamlit | Streamlit → FastAPI → DB | Established pattern | Separation of concerns, reusable API |

**Deprecated/outdated:**
- `use_container_width=True` in `st.plotly_chart`: use `width="stretch"` (Streamlit 1.55)
- APScheduler 4.x for this project: different API, async-first — 3.x is better fit

---

## Open Questions

1. **New/removed product definition ambiguity**
   - What we know: `ScrapeRun` has `products_new` and `products_removed` counters, but no FK linking to which specific products changed
   - What's unclear: The schema doesn't have a `scrape_run_id` foreign key on `Product`, so there's no direct way to join "products that appeared in run X"
   - Recommendation: Use heuristic — "new" = products with `first_seen_at` within last 8 days; "removed" = products with `is_active=False` and `updated_at` within last 8 days. This is an approximation but works for the use case. If exact tracking is needed, add `first_scrape_run_id` FK to `Product` model (a Alembic migration would be needed).

2. **Timezone for APScheduler cron**
   - What we know: The team is Russian, server may be UTC
   - What's unclear: Server timezone vs. business hours timezone
   - Recommendation: Use `timezone="Europe/Moscow"` in CronTrigger so Monday 3:00 AM means Moscow time, not UTC.

3. **Streamlit and FastAPI on same port vs separate**
   - What we know: Streamlit runs on 8501, FastAPI on 8000 by default
   - What's unclear: Production deployment target (VM? Docker?)
   - Recommendation: Run both in Docker Compose with separate services. Streamlit container calls FastAPI container via service name. Expose only Streamlit on external port if desired, or both.

4. **Ormatek scraper in background trigger**
   - What we know: Ormatek scraper uses `subprocess.run()` with `uv run --python 3.11` — blocking subprocess in `run_scrapers.main()`
   - What's unclear: Whether this is safe to call from a daemon thread (APScheduler BackgroundScheduler)
   - Recommendation: Should be fine — `subprocess.run()` in a thread works; the thread simply blocks until subprocess completes. No asyncio conflict.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | none (uses conftest.py) |
| Quick run command | `pytest tests/test_api.py -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DASH-01 | GET /api/prices returns rows filterable by site | unit | `pytest tests/test_api.py::test_get_prices -x` | Wave 0 |
| DASH-02 | GET /api/prices returns price history with scraped_at | unit | `pytest tests/test_api.py::test_get_price_history -x` | Wave 0 |
| DASH-03 | GET /api/export returns valid xlsx bytes | unit | `pytest tests/test_api.py::test_export_excel -x` | Wave 0 |
| DASH-04 | GET /api/prices includes avg price_sale per site | unit | `pytest tests/test_api.py::test_price_index -x` | Wave 0 |
| DASH-05 | GET /api/runs returns latest run with finished_at | unit | `pytest tests/test_api.py::test_freshness_data -x` | Wave 0 |
| DASH-06 | GET /api/products/changes returns new/removed lists | unit | `pytest tests/test_api.py::test_product_changes -x` | Wave 0 |
| SCHD-01 | APScheduler job registered with correct CronTrigger | unit | `pytest tests/test_scheduler.py::test_cron_trigger -x` | Wave 0 |
| SCHD-02 | GET /api/runs returns all runs ordered by started_at | unit | `pytest tests/test_api.py::test_get_runs -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_api.py -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_api.py` — covers DASH-01 through DASH-06, SCHD-02 (FastAPI TestClient tests with SQLite in-memory)
- [ ] `tests/test_scheduler.py` — covers SCHD-01 (verifies job is added to scheduler with correct trigger params)
- [ ] `httpx` or `requests` install — needed for FastAPI TestClient in `tests/test_api.py`

*(Existing `conftest.py` with SQLite in-memory fixture is reusable for API tests via FastAPI's TestClient)*

---

## Sources

### Primary (HIGH confidence)
- Streamlit official docs (docs.streamlit.io) — st.tabs, st.plotly_chart, st.dataframe, st.download_button, st.metric, colored text syntax
- APScheduler 3.x official docs (apscheduler.readthedocs.io/en/3.x) — BackgroundScheduler, CronTrigger, lifespan integration
- FastAPI official docs (fastapi.tiangolo.com) — BackgroundTasks, lifespan, Depends, StreamingResponse
- Plotly Express official docs (plotly.com/python) — px.line, px.box, px.histogram

### Secondary (MEDIUM confidence)
- Streamlit 2026 release notes — confirmed version 1.55.0 as latest, deprecation of use_container_width
- APScheduler PyPI — confirmed 3.11.2.post1 as latest 3.x version
- Multiple Streamlit community posts — confirmed BytesIO + to_excel + download_button pattern

### Tertiary (LOW confidence)
- WebSearch results on FastAPI + Streamlit architecture — Streamlit-calls-FastAPI pattern confirmed by multiple sources but not official docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are official, versions verified on PyPI and release notes
- Architecture: HIGH — patterns directly from official FastAPI and Streamlit docs
- Pitfalls: HIGH — APScheduler/asyncio conflict verified by official APScheduler docs; Decimal issue confirmed by FastAPI GitHub discussions
- New/removed product detection: MEDIUM — workaround based on schema analysis; exact logic depends on data patterns not yet tested

**Research date:** 2026-03-15
**Valid until:** 2026-06-15 (stable libraries; Streamlit releases frequently but API is backward compatible)
