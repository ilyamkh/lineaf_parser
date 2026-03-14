"""Unit tests for scrapers pipeline: parse_price, validate_product, upsert, change detection."""

from decimal import Decimal

import pytest

from lineaf.scrapers.utils import parse_price, validate_product
from lineaf.scrapers.pipeline import (
    insert_price_snapshot,
    mark_removed_products,
    upsert_product,
)
from lineaf.models.product import Product
from lineaf.models.price_snapshot import PriceSnapshot
from lineaf.models.scrape_run import ScrapeRun


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_product_data():
    """Return a dict with all Product fields for testing."""
    return {
        "source_site": "test",
        "source_url": "http://test.com/mattress-1",
        "name": "Test Mattress 160x200",
        "firmness": "medium",
        "height_cm": "20",
        "filler": "foam",
        "cover_material": "cotton",
        "weight_kg": "15",
    }


@pytest.fixture()
def scrape_run(db_session):
    """Create a ScrapeRun row and return its id."""
    run = ScrapeRun(site="test", status="running")
    db_session.add(run)
    db_session.flush()
    return run.id


# ---------------------------------------------------------------------------
# parse_price tests
# ---------------------------------------------------------------------------


class TestParsePrice:
    def test_russian_price_with_spaces(self):
        assert parse_price("25 180 \u20bd") == Decimal("25180")

    def test_zero_price(self):
        assert parse_price("0 \u20bd") == Decimal("0")

    def test_empty_string(self):
        assert parse_price("") is None

    def test_none(self):
        assert parse_price(None) is None

    def test_price_with_comma_decimal(self):
        assert parse_price("12 345,67 \u0440\u0443\u0431.") == Decimal("12345.67")

    def test_plain_integer(self):
        assert parse_price("5000") == Decimal("5000")

    def test_garbage_text(self):
        assert parse_price("no digits here") is None


# ---------------------------------------------------------------------------
# validate_product tests
# ---------------------------------------------------------------------------


class TestValidateProduct:
    def test_valid_with_both_prices(self):
        assert validate_product({"name": "M1", "price_sale": Decimal("100"), "price_original": Decimal("200")}) is True

    def test_valid_with_sale_only(self):
        assert validate_product({"name": "M1", "price_sale": Decimal("100"), "price_original": None}) is True

    def test_valid_with_original_only(self):
        assert validate_product({"name": "M1", "price_sale": None, "price_original": Decimal("200")}) is True

    def test_invalid_no_name(self):
        assert validate_product({"name": "", "price_sale": Decimal("100"), "price_original": None}) is False

    def test_invalid_no_prices(self):
        assert validate_product({"name": "M1", "price_sale": None, "price_original": None}) is False

    def test_invalid_missing_name_key(self):
        assert validate_product({"price_sale": Decimal("100")}) is False


# ---------------------------------------------------------------------------
# upsert_product tests
# ---------------------------------------------------------------------------


class TestUpsertProduct:
    def test_insert_new_product(self, db_session, sample_product_data):
        pid = upsert_product(db_session, sample_product_data)
        assert pid > 0
        product = db_session.get(Product, pid)
        assert product.name == "Test Mattress 160x200"
        assert product.is_active is True

    def test_update_existing_product(self, db_session, sample_product_data):
        pid1 = upsert_product(db_session, sample_product_data)
        updated = sample_product_data.copy()
        updated["name"] = "Updated Mattress"
        pid2 = upsert_product(db_session, updated)
        assert pid1 == pid2
        product = db_session.get(Product, pid1)
        assert product.name == "Updated Mattress"

    def test_reactivate_inactive_product(self, db_session, sample_product_data):
        pid = upsert_product(db_session, sample_product_data)
        product = db_session.get(Product, pid)
        product.is_active = False
        db_session.flush()
        # Upsert should reactivate
        pid2 = upsert_product(db_session, sample_product_data)
        assert pid == pid2
        db_session.refresh(product)
        assert product.is_active is True


# ---------------------------------------------------------------------------
# insert_price_snapshot tests
# ---------------------------------------------------------------------------


class TestInsertPriceSnapshot:
    def test_creates_snapshot(self, db_session, sample_product_data, scrape_run):
        pid = upsert_product(db_session, sample_product_data)
        insert_price_snapshot(
            db_session,
            product_id=pid,
            scrape_run_id=scrape_run,
            price_original=Decimal("30000"),
            price_sale=Decimal("25000"),
        )
        db_session.flush()
        snap = db_session.query(PriceSnapshot).filter_by(product_id=pid).first()
        assert snap is not None
        assert snap.price_original == Decimal("30000")
        assert snap.price_sale == Decimal("25000")
        assert snap.scrape_run_id == scrape_run


# ---------------------------------------------------------------------------
# mark_removed_products tests
# ---------------------------------------------------------------------------


class TestMarkRemovedProducts:
    def test_marks_missing_products_inactive(self, db_session, sample_product_data):
        upsert_product(db_session, sample_product_data)
        data2 = sample_product_data.copy()
        data2["source_url"] = "http://test.com/mattress-2"
        data2["name"] = "Second Mattress"
        upsert_product(db_session, data2)
        db_session.flush()
        # Only mattress-2 is in current scrape
        removed = mark_removed_products(
            db_session, "test", {"http://test.com/mattress-2"}
        )
        assert removed == 1
        p1 = db_session.query(Product).filter_by(source_url="http://test.com/mattress-1").one()
        assert p1.is_active is False
        p2 = db_session.query(Product).filter_by(source_url="http://test.com/mattress-2").one()
        assert p2.is_active is True

    def test_empty_scraped_urls_no_deactivation(self, db_session, sample_product_data):
        upsert_product(db_session, sample_product_data)
        db_session.flush()
        removed = mark_removed_products(db_session, "test", set())
        assert removed == 0
        p = db_session.query(Product).filter_by(source_url="http://test.com/mattress-1").one()
        assert p.is_active is True
