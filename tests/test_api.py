"""Tests for the FastAPI REST API endpoints."""

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from lineaf.models import Base, Product, PriceSnapshot, ScrapeRun

# ---------------------------------------------------------------------------
# Test database setup — override FastAPI get_db dependency with SQLite
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///:memory:")

engine = create_engine(TEST_DATABASE_URL, echo=False)
Base.metadata.create_all(engine)

from fastapi.testclient import TestClient  # noqa: E402

from lineaf.database import get_db  # noqa: E402
from lineaf.main import app  # noqa: E402


def override_get_db():
    with Session(bind=engine) as session:
        yield session
        session.rollback()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc)
TWO_DAYS_AGO = NOW - timedelta(days=2)
TEN_DAYS_AGO = NOW - timedelta(days=10)


@pytest.fixture(autouse=True)
def seed_data():
    """Seed DB before each test, clean up after."""
    with Session(bind=engine) as s:
        # Scrape runs
        run_ok = ScrapeRun(
            id=1, site="askona", status="success",
            started_at=TWO_DAYS_AGO, finished_at=TWO_DAYS_AGO,
            products_found=10, products_new=2, products_removed=0,
        )
        run_err = ScrapeRun(
            id=2, site="sonum", status="error",
            started_at=TEN_DAYS_AGO, finished_at=TEN_DAYS_AGO,
            error_message="timeout",
        )
        s.add_all([run_ok, run_err])
        s.flush()

        # Active products
        p1 = Product(
            id=1, source_site="askona", source_url="https://askona.ru/m1",
            name="Askona Model A", is_active=True,
            first_seen_at=TWO_DAYS_AGO,
        )
        p2 = Product(
            id=2, source_site="sonum", source_url="https://sonum.ru/m1",
            name="Sonum Model B", is_active=True,
            first_seen_at=TEN_DAYS_AGO,
        )
        # Inactive (removed) product
        p3 = Product(
            id=3, source_site="askona", source_url="https://askona.ru/m2",
            name="Askona Removed", is_active=False,
            first_seen_at=TEN_DAYS_AGO, updated_at=TWO_DAYS_AGO,
        )
        s.add_all([p1, p2, p3])
        s.flush()

        # Price snapshots — 2 per active product
        snaps = [
            PriceSnapshot(
                id=1, product_id=1, scraped_at=TEN_DAYS_AGO,
                scrape_run_id=1,
                price_original=Decimal("15000.00"), price_sale=Decimal("12000.00"),
            ),
            PriceSnapshot(
                id=2, product_id=1, scraped_at=TWO_DAYS_AGO,
                scrape_run_id=1,
                price_original=Decimal("15000.00"), price_sale=Decimal("11000.00"),
            ),
            PriceSnapshot(
                id=3, product_id=2, scraped_at=TEN_DAYS_AGO,
                scrape_run_id=2,
                price_original=Decimal("20000.00"), price_sale=Decimal("18000.00"),
            ),
            PriceSnapshot(
                id=4, product_id=2, scraped_at=TWO_DAYS_AGO,
                scrape_run_id=2,
                price_original=Decimal("20000.00"), price_sale=Decimal("17000.00"),
            ),
        ]
        s.add_all(snaps)
        s.commit()

    yield

    # Teardown
    with Session(bind=engine) as s:
        s.query(PriceSnapshot).delete()
        s.query(Product).delete()
        s.query(ScrapeRun).delete()
        s.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_get_prices():
    """GET /api/prices returns latest snapshot per active product."""
    resp = client.get("/api/prices")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2  # 2 active products
    # Check fields
    item = data[0]
    for field in ("product_id", "name", "source_site", "price_sale",
                  "price_original", "scraped_at"):
        assert field in item, f"Missing field: {field}"
    # Decimal values must be floats
    assert isinstance(item["price_sale"], float)
    assert isinstance(item["price_original"], float)


def test_get_prices_filter_site():
    """GET /api/prices?site=askona returns only askona products."""
    resp = client.get("/api/prices", params={"site": "askona"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["source_site"] == "askona"


def test_get_price_history():
    """GET /api/prices/history?product_id=1 returns all snapshots ordered by scraped_at."""
    resp = client.get("/api/prices/history", params={"product_id": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Ordered by scraped_at asc
    assert data[0]["scraped_at"] < data[1]["scraped_at"]
    assert isinstance(data[0]["price_sale"], float)


def test_price_index():
    """GET /api/prices/index returns avg price_sale per source_site."""
    resp = client.get("/api/prices/index")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    sites = {d["site"] for d in data}
    assert "askona" in sites
    assert "sonum" in sites
    for item in data:
        assert isinstance(item["avg_price_sale"], float)


def test_export_excel():
    """GET /api/export returns xlsx bytes."""
    resp = client.get("/api/export")
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"] or \
           "application/vnd.openxmlformats" in resp.headers["content-type"]
    assert len(resp.content) > 100  # non-trivial file


def test_freshness_data():
    """GET /api/runs/freshness returns latest successful run per site."""
    resp = client.get("/api/runs/freshness")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    by_site = {d["site"]: d for d in data}
    # askona had a successful run 2 days ago — not stale
    assert by_site["askona"]["is_stale"] is False
    assert by_site["askona"]["last_success"] is not None
    # sonum had only error run — stale
    assert by_site["sonum"]["is_stale"] is True


def test_product_changes():
    """GET /api/products/changes returns new and removed products."""
    resp = client.get("/api/products/changes")
    assert resp.status_code == 200
    data = resp.json()
    assert "new" in data
    assert "removed" in data
    # p1 is new (first_seen_at = 2 days ago, within 8 days)
    new_names = [p["name"] for p in data["new"]]
    assert "Askona Model A" in new_names
    # p3 is removed (is_active=False)
    removed_names = [p["name"] for p in data["removed"]]
    assert "Askona Removed" in removed_names


def test_get_runs():
    """GET /api/runs returns scrape runs ordered by started_at desc."""
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    # Ordered desc by started_at
    assert data[0]["started_at"] >= data[1]["started_at"]
