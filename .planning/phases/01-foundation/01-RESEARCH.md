# Phase 1: Foundation - Research

**Researched:** 2026-03-14
**Domain:** Python project scaffold (uv), PostgreSQL schema, SQLAlchemy 2.0 ORM, Alembic migrations, Docker Compose local dev
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Fields missing on some sites must accept NULL — not all 3 competitors will have every field
- Field names must be normalized (unified naming across sites)
- Firmness/height/filler/cover/weight stored as TEXT — values differ across sites, no reliable enum
- No seed data from Excel in this phase — that is Phase 2 territory

### Claude's Discretion
- Docker vs local PostgreSQL setup
- Dependency management tool (uv recommended)
- Alembic configuration details
- All infrastructure decisions (Docker setup, project structure, Alembic config, SQLAlchemy models)

### Deferred Ideas (OUT OF SCOPE)
- Site structure research (askona.ru, ormatek.ru, sonum.ru) — Phase 2
- Handling missing/different field names across sites — Phase 2 spider implementation
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STOR-01 | БД хранит каталог продуктов с дедупликацией (таблица products) | SQLAlchemy model with unique constraint on (source_site, source_url), UPSERT pattern via ON CONFLICT |
| STOR-02 | БД хранит историю снапшотов цен с привязкой к дате сбора (таблица price_snapshots) | price_snapshots table with FK to products.id and scraped_at TIMESTAMP WITH TIME ZONE |
| STOR-03 | БД хранит лог запусков парсера с результатами (таблица scrape_runs) | scrape_runs table with status enum or TEXT, started_at/finished_at timestamps, counts |
| STOR-04 | Схема БД поддерживает отслеживание статуса активности товара (is_active) | is_active BOOLEAN NOT NULL DEFAULT TRUE on products table |
</phase_requirements>

---

## Summary

Phase 1 delivers a stable database contract for the entire project. The work splits cleanly into two plans: scaffolding the Python project with uv and Docker Compose (Plan 01-01), and defining SQLAlchemy 2.0 models with Alembic migrations (Plan 01-02).

The recommended stack is uv for dependency management, SQLAlchemy 2.0 declarative ORM with `mapped_column()` and `Mapped[]` type annotations, Alembic for migrations, pydantic-settings for config, and a Docker Compose file that starts only PostgreSQL (the app runs locally via `uv run`). This is a greenfield project — no existing code to migrate.

The most critical design decision in this phase is the schema. The `products` table is the system's deduplication anchor: products are identified by `(source_site, source_url)` unique key. Price history is append-only in `price_snapshots`. The `scrape_runs` table provides operational logging. All nullable product attribute columns (firmness, height, filler, cover material, weight) are TEXT to accommodate heterogeneous competitor data.

**Primary recommendation:** Use `uv init`, SQLAlchemy 2.0 DeclarativeBase + `mapped_column()`, Alembic autogenerate with env.py reading DATABASE_URL from .env via python-dotenv. PostgreSQL runs in Docker Compose; the app and Alembic run on the host via `uv run`.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| uv | latest (0.5+) | Package manager, venv, lock file | 10-100x faster than pip; replaces pip+virtualenv+pip-tools; single tool |
| SQLAlchemy | 2.0.x | ORM + Core for all DB access | Industry standard; 2.0 style is fully typed; Alembic integration |
| Alembic | 1.13+ | Database schema migrations | Official SQLAlchemy migration tool; autogenerate support |
| psycopg2-binary | 2.9.x | PostgreSQL driver for SQLAlchemy | Most stable sync driver; binary wheel avoids libpq dependency |
| pydantic-settings | 2.x | Config from .env + env vars | Type-safe settings; integrates with FastAPI; replaces python-dotenv |
| python-dotenv | 1.x | Load .env in Alembic env.py | Alembic's env.py runs outside FastAPI; dotenv needed there |
| FastAPI | 0.110+ | Web framework (scaffold only) | Chosen stack per PROJECT.md |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 7.x / 8.x | Test runner | All test phases; standard |
| pytest-asyncio | 0.23+ | Async test support | If async SQLAlchemy sessions used later |
| psycopg (psycopg3) | 3.x | Alternative async PostgreSQL driver | Prefer if adding async DB access in Phase 2/3 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| psycopg2-binary | asyncpg | asyncpg is async-only; Phase 1 uses sync Alembic migrations; psycopg2 is safer for initial setup |
| pydantic-settings | plain python-dotenv | pydantic-settings provides type validation; preferred for FastAPI projects |
| Docker Compose for PostgreSQL only | Full stack Docker | App runs on host = faster iteration; no rebuild cycle during development |

**Installation:**
```bash
uv init lineaf-parser
cd lineaf-parser
uv add sqlalchemy alembic psycopg2-binary pydantic-settings python-dotenv fastapi uvicorn
uv add --dev pytest pytest-asyncio
```

---

## Architecture Patterns

### Recommended Project Structure

```
lineaf-parser/
├── .env                    # DATABASE_URL and local secrets (gitignored)
├── .env.example            # Template committed to git
├── .python-version         # Python version pin (created by uv)
├── .gitignore
├── pyproject.toml          # Project metadata and dependencies (uv managed)
├── uv.lock                 # Locked dependency versions (commit to git)
├── docker-compose.yml      # PostgreSQL only
├── alembic.ini             # Alembic config (sqlalchemy.url placeholder)
├── alembic/
│   ├── env.py              # Reads DATABASE_URL from .env
│   ├── script.py.mako
│   └── versions/
│       └── 0001_initial_schema.py
├── src/
│   └── lineaf/
│       ├── __init__.py
│       ├── config.py       # pydantic-settings Settings class
│       ├── database.py     # engine + SessionLocal + get_db
│       ├── models/
│       │   ├── __init__.py
│       │   ├── base.py     # DeclarativeBase
│       │   ├── product.py
│       │   ├── price_snapshot.py
│       │   └── scrape_run.py
│       └── main.py         # FastAPI app (stub)
└── tests/
    ├── conftest.py         # engine fixture, session fixture
    └── test_models.py      # round-trip insert test
```

### Pattern 1: SQLAlchemy 2.0 Declarative Models

**What:** Use `DeclarativeBase` + `Mapped[]` type annotations + `mapped_column()` for all models. This is the modern SQLAlchemy 2.0 style; the legacy `Column()` syntax still works but is not recommended for new code.

**When to use:** All model definitions in this project.

**Example — products table:**
```python
# Source: https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import NUMERIC, Boolean, DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_site: Mapped[str] = mapped_column(String(50), nullable=False)   # 'askona', 'ormatek', 'sonum'
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)

    # Normalized attributes — nullable because not all sites expose all fields
    firmness: Mapped[Optional[str]] = mapped_column(String(256))
    height_cm: Mapped[Optional[str]] = mapped_column(String(64))
    filler: Mapped[Optional[str]] = mapped_column(String(512))
    cover_material: Mapped[Optional[str]] = mapped_column(String(256))
    weight_kg: Mapped[Optional[str]] = mapped_column(String(64))

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        # Deduplication anchor: same product = same site + URL
        UniqueConstraint("source_site", "source_url", name="uq_products_site_url"),
    )
```

**Example — price_snapshots table:**
```python
from sqlalchemy import ForeignKey, UniqueConstraint

class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    scraped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scrape_run_id: Mapped[Optional[int]] = mapped_column(ForeignKey("scrape_runs.id"))

    # NUMERIC(12,2) — never float or text for currency
    price_original: Mapped[Optional[Decimal]] = mapped_column(NUMERIC(12, 2))
    price_sale: Mapped[Optional[Decimal]] = mapped_column(NUMERIC(12, 2))
```

**Example — scrape_runs table:**
```python
class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    site: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    products_found: Mapped[Optional[int]]
    products_new: Mapped[Optional[int]]
    products_removed: Mapped[Optional[int]]
    error_message: Mapped[Optional[str]] = mapped_column(String(2048))
```

### Pattern 2: Alembic env.py Reading DATABASE_URL from .env

**What:** Override `sqlalchemy.url` in env.py at runtime, reading from environment via python-dotenv. Never hardcode credentials in alembic.ini.

**Example:**
```python
# alembic/env.py (key section)
import os
from dotenv import load_dotenv

load_dotenv()  # loads .env from cwd

config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
```

### Pattern 3: pydantic-settings Config

**What:** Centralized, typed config with .env file support and validation.

**Example:**
```python
# src/lineaf/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str
    debug: bool = False


settings = Settings()
```

### Pattern 4: Docker Compose — PostgreSQL Only

**What:** Only the database runs in Docker. The app and Alembic run locally via `uv run`. This avoids image rebuild cycles during development.

**Example:**
```yaml
# docker-compose.yml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: lineaf
      POSTGRES_PASSWORD: lineaf
      POSTGRES_DB: lineaf_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U lineaf -d lineaf_dev"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

**.env file:**
```
DATABASE_URL=postgresql://lineaf:lineaf@localhost:5432/lineaf_dev
```

### Anti-Patterns to Avoid

- **Float for prices:** Never use `Float` or `float` for monetary values. PostgreSQL `NUMERIC(12,2)` and Python `Decimal` are the only correct choices. Float introduces rounding errors.
- **Hardcoding DATABASE_URL in alembic.ini:** Credentials in version control leak secrets. Always use env vars.
- **SQLAlchemy 1.x style `Column()`:** Legacy syntax still works but mixes poorly with 2.0 `Mapped[]` annotations. Use `mapped_column()` exclusively.
- **Importing models in env.py without Base.metadata:** Alembic autogenerate only detects tables registered in `target_metadata`. Must import all model modules before running autogenerate.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema migrations | Custom SQL upgrade scripts | Alembic | Tracks version, supports down-migrations, autogenerates from models |
| Env var loading + validation | Custom config parser | pydantic-settings | Type coercion, missing-var errors, .env file support |
| Package/venv management | pip + virtualenv manually | uv | Lock file reproducibility, 10-100x faster |
| UPSERT (deduplication) | SELECT then INSERT/UPDATE | PostgreSQL `ON CONFLICT DO UPDATE` | Atomic; no race conditions |

**Key insight:** The UPSERT pattern for products deduplication (`INSERT ... ON CONFLICT (source_site, source_url) DO UPDATE SET ...`) is a single SQL statement and avoids race conditions that a SELECT-then-INSERT approach cannot.

---

## Common Pitfalls

### Pitfall 1: Alembic autogenerate misses tables

**What goes wrong:** Running `alembic revision --autogenerate` produces an empty migration even though models exist.

**Why it happens:** env.py `target_metadata` is set to `Base.metadata` but model modules were never imported, so no tables are registered.

**How to avoid:** In `alembic/env.py`, explicitly import all model modules before referencing `Base.metadata`:
```python
from lineaf.models import base, product, price_snapshot, scrape_run  # noqa: F401
from lineaf.models.base import Base
target_metadata = Base.metadata
```

**Warning signs:** Migration file shows `pass` inside `upgrade()`.

### Pitfall 2: Float for NUMERIC prices

**What goes wrong:** Prices stored as `float` accumulate rounding errors (e.g., 9999.99 becomes 9999.9900000000001).

**Why it happens:** Python `float` is IEEE 754 double, which cannot represent most decimal fractions exactly.

**How to avoid:** Always use `NUMERIC(12,2)` in the SQLAlchemy column definition and `Decimal` in Python. The `psycopg2` driver returns `Decimal` for `NUMERIC` columns automatically.

**Warning signs:** Any use of `Float` type in model definitions; any column annotated as `Mapped[float]` for prices.

### Pitfall 3: Missing `onupdate` for updated_at

**What goes wrong:** `updated_at` timestamp stays at insertion time even after updates, making freshness indicators in the dashboard incorrect.

**Why it happens:** `server_default=func.now()` only fires on INSERT; `onupdate` must be set separately for UPDATE triggers.

**How to avoid:** Use both `server_default=func.now()` and `onupdate=func.now()` on `updated_at`, or create a PostgreSQL trigger. SQLAlchemy `onupdate` handles this at the ORM layer.

### Pitfall 4: psycopg2-binary in production

**What goes wrong:** `psycopg2-binary` ships its own bundled libpq which can conflict with system libraries in production.

**Why it happens:** The binary wheel is designed for development convenience, not production.

**How to avoid:** Use `psycopg2-binary` for local development (this phase). Flag for replacement with `psycopg2` (compiled against system libpq) when deploying to VM.

### Pitfall 5: Docker healthcheck not awaited

**What goes wrong:** Alembic connects to PostgreSQL before it finishes initializing, causing "connection refused" errors on first `docker-compose up`.

**Why it happens:** Docker Compose `depends_on` without `condition: service_healthy` only waits for the container to start, not for PostgreSQL to be ready.

**How to avoid:** Add `healthcheck` to the `db` service in docker-compose.yml and use `condition: service_healthy` in any dependent service. For local dev where Alembic runs on the host, just wait a few seconds or poll with `pg_isready`.

---

## Code Examples

Verified patterns from official sources:

### Alembic env.py — full critical section

```python
# alembic/env.py
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Load .env so DATABASE_URL is available
load_dotenv()

# Import all models so Alembic sees their metadata
from lineaf.models import product, price_snapshot, scrape_run  # noqa: F401
from lineaf.models.base import Base

config = context.config

# Override sqlalchemy.url from environment — never use alembic.ini for credentials
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### database.py — engine and session factory

```python
# src/lineaf/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from lineaf.config import settings

engine = create_engine(settings.database_url, echo=settings.debug)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Round-trip test pattern

```python
# tests/test_models.py
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from lineaf.models.base import Base
from lineaf.models.product import Product
from lineaf.models.price_snapshot import PriceSnapshot


def test_product_price_snapshot_round_trip(db_session: Session):
    product = Product(
        source_site="askona",
        source_url="https://askona.ru/product/1",
        name="Test Mattress",
        is_active=True,
    )
    db_session.add(product)
    db_session.flush()

    snapshot = PriceSnapshot(
        product_id=product.id,
        scraped_at=datetime.now(UTC),
        price_original=Decimal("29999.00"),
        price_sale=Decimal("24999.99"),
    )
    db_session.add(snapshot)
    db_session.commit()

    fetched = db_session.get(Product, product.id)
    assert fetched.is_active is True
    assert fetched.price_snapshots[0].price_sale == Decimal("24999.99")
```

### pyproject.toml structure

```toml
[project]
name = "lineaf-parser"
version = "0.1.0"
description = "Competitor price monitoring for Lineaf mattress brand"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "psycopg2-binary>=2.9",
    "pydantic-settings>=2.0",
    "python-dotenv>=1.0",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `Column()` + `declarative_base()` | `mapped_column()` + `DeclarativeBase` + `Mapped[]` | SQLAlchemy 2.0 (2023) | Full IDE type checking; cleaner syntax |
| `requirements.txt` + pip | `pyproject.toml` + uv.lock | 2024-2025 | Single tool; 10-100x faster installs |
| `BaseSettings` from pydantic v1 | `pydantic-settings` separate package | Pydantic v2 (2023) | Must `pip install pydantic-settings`, not just pydantic |
| `docker-compose` v1 CLI | `docker compose` v2 (plugin) | Docker Desktop 3.x+ | `docker-compose` is deprecated; use `docker compose` |

**Deprecated/outdated:**
- `declarative_base()` from `sqlalchemy.ext.declarative`: Still functional but legacy. Use `DeclarativeBase` class from `sqlalchemy.orm`.
- `psycopg2` compile-from-source: Fine for production VM, painful for local dev. Use `psycopg2-binary` locally.

---

## Open Questions

1. **Python version to pin**
   - What we know: uv supports Python 3.8+; pydantic-settings v2 requires 3.8+; project is greenfield
   - What's unclear: Team's installed Python version
   - Recommendation: Pin to 3.11 in `.python-version` — stable LTS, widely available, good typing support

2. **asyncpg vs psycopg2 for Phase 2+**
   - What we know: Playwright scrapers will be async; FastAPI supports both sync and async routes
   - What's unclear: Whether Phase 3 dashboard will need async DB access
   - Recommendation: Start with psycopg2-binary (sync) now; migrate to psycopg (v3) in Phase 2/3 if async DB is needed — schema is driver-agnostic

3. **`updated_at` trigger: SQLAlchemy `onupdate` vs PostgreSQL trigger**
   - What we know: SQLAlchemy `onupdate=func.now()` fires at ORM layer but is bypassed by raw SQL updates
   - What's unclear: Whether any pipeline will issue raw SQL UPDATEs (e.g., direct psycopg2 calls in Phase 2)
   - Recommendation: Use SQLAlchemy `onupdate` for now; note in schema that a PostgreSQL trigger is the robust alternative if raw SQL updates are introduced

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` — Wave 0 creates it |
| Quick run command | `uv run pytest tests/test_models.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STOR-01 | products table exists with correct columns; UNIQUE constraint on (source_site, source_url) prevents duplicate inserts | unit | `uv run pytest tests/test_models.py::test_product_deduplication -x` | Wave 0 |
| STOR-02 | price_snapshots row with price_original and price_sale as NUMERIC(12,2) inserts and retrieves as Decimal | unit | `uv run pytest tests/test_models.py::test_price_snapshot_decimal -x` | Wave 0 |
| STOR-03 | scrape_runs row with status, timestamps, and counts inserts correctly | unit | `uv run pytest tests/test_models.py::test_scrape_run_insert -x` | Wave 0 |
| STOR-04 | is_active column exists on products, defaults to True, can be set to False | unit | `uv run pytest tests/test_models.py::test_is_active_flag -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_models.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/conftest.py` — engine fixture pointing at test DB (separate from dev DB), session fixture with rollback teardown
- [ ] `tests/test_models.py` — covers STOR-01 through STOR-04
- [ ] Framework install: `uv add --dev pytest` — no pytest detected yet (greenfield)
- [ ] Test DB URL: add `TEST_DATABASE_URL` to `.env.example`; conftest reads it or creates a `lineaf_test` database

---

## Sources

### Primary (HIGH confidence)

- SQLAlchemy 2.0 official docs — https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html — DeclarativeBase, Mapped, mapped_column patterns
- Alembic official tutorial — https://alembic.sqlalchemy.org/en/latest/tutorial.html — init steps, env.py structure, migration commands
- Alembic autogenerate docs — https://alembic.sqlalchemy.org/en/latest/autogenerate.html — autogenerate behavior and limitations
- uv official docs — https://docs.astral.sh/uv/guides/projects/ — project init, dependency management commands
- FastAPI settings docs — https://fastapi.tiangolo.com/advanced/settings/ — pydantic-settings pattern with lru_cache

### Secondary (MEDIUM confidence)

- pydantic-settings docs — https://docs.pydantic.dev/latest/concepts/pydantic_settings/ — BaseSettings, SettingsConfigDict, env_file
- Alembic env.py + dotenv pattern — https://allan-simon.github.io/blog/posts/python-alembic-with-environment-variables/ — verified consistent with official Alembic config docs
- Docker Compose PostgreSQL healthcheck pattern — verified across multiple sources (2025-2026 articles)

### Tertiary (LOW confidence)

- psycopg2-binary production warning — widely cited community practice; not directly in official psycopg2 docs but consistent across PyPI description and multiple tutorials

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — uv, SQLAlchemy 2.0, Alembic, pydantic-settings all verified with official docs
- Architecture: HIGH — patterns derived from official docs and confirmed across multiple current sources
- Schema design: HIGH — NUMERIC(12,2) for prices, UNIQUE constraint for deduplication are standard PostgreSQL/SQLAlchemy patterns
- Pitfalls: MEDIUM — most verified with official docs; psycopg2-binary production pitfall is community-validated

**Research date:** 2026-03-14
**Valid until:** 2026-09-14 (stable ecosystem — SQLAlchemy, Alembic, uv all have stable release cadences)
