"""Tests for STOR-01 through STOR-04 requirements."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from lineaf.models.price_snapshot import PriceSnapshot
from lineaf.models.product import Product
from lineaf.models.scrape_run import ScrapeRun


class TestProductDeduplication:
    """STOR-01: Duplicate (source_site, source_url) raises IntegrityError."""

    def test_product_deduplication(self, db_session):
        p1 = Product(
            source_site="askona",
            source_url="https://askona.ru/p/1",
            name="Mattress One",
        )
        db_session.add(p1)
        db_session.flush()

        p2 = Product(
            source_site="askona",
            source_url="https://askona.ru/p/1",
            name="Mattress Duplicate",
        )
        db_session.add(p2)
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestPriceSnapshotDecimal:
    """STOR-02: Prices stored and retrieved as Python Decimal, not float."""

    def test_price_snapshot_decimal(self, db_session):
        product = Product(
            source_site="askona",
            source_url="https://askona.ru/p/decimal-test",
            name="Decimal Test Mattress",
        )
        db_session.add(product)
        db_session.flush()

        snapshot = PriceSnapshot(
            product_id=product.id,
            scraped_at=datetime.now(timezone.utc),
            price_original=Decimal("29999.00"),
            price_sale=Decimal("24999.99"),
        )
        db_session.add(snapshot)
        db_session.commit()

        # Re-query to ensure round-trip
        db_session.expire_all()
        result = db_session.get(PriceSnapshot, snapshot.id)

        assert result.price_original == Decimal("29999.00")
        assert result.price_sale == Decimal("24999.99")
        assert isinstance(result.price_original, Decimal)
        assert isinstance(result.price_sale, Decimal)


class TestScrapeRunInsert:
    """STOR-03: ScrapeRun stores status, timestamps, and item counts."""

    def test_scrape_run_insert(self, db_session):
        run = ScrapeRun(
            site="askona",
            status="success",
            products_found=42,
            products_new=3,
            products_removed=1,
        )
        db_session.add(run)
        db_session.commit()

        db_session.expire_all()
        result = db_session.get(ScrapeRun, run.id)

        assert result.site == "askona"
        assert result.status == "success"
        assert result.products_found == 42
        assert result.products_new == 3
        assert result.products_removed == 1


class TestIsActiveFlag:
    """STOR-04: is_active defaults True and can be set to False."""

    def test_is_active_flag(self, db_session):
        product = Product(
            source_site="ormatek",
            source_url="https://ormatek.ru/p/active-test",
            name="Active Test Mattress",
        )
        db_session.add(product)
        db_session.commit()

        # Default should be True
        db_session.expire_all()
        result = db_session.get(Product, product.id)
        assert result.is_active is True

        # Set to False
        result.is_active = False
        db_session.commit()

        db_session.expire_all()
        result = db_session.get(Product, product.id)
        assert result.is_active is False


class TestProductPriceSnapshotRoundTrip:
    """Round-trip: insert Product + PriceSnapshot, query via relationship."""

    def test_product_price_snapshot_round_trip(self, db_session):
        product = Product(
            source_site="sonum",
            source_url="https://sonum.ru/p/roundtrip",
            name="Round Trip Mattress",
        )
        db_session.add(product)
        db_session.flush()

        snapshot = PriceSnapshot(
            product_id=product.id,
            scraped_at=datetime.now(timezone.utc),
            price_original=Decimal("15000.00"),
            price_sale=Decimal("12999.50"),
        )
        db_session.add(snapshot)
        db_session.commit()

        db_session.expire_all()
        result = db_session.get(Product, product.id)
        assert len(result.price_snapshots) == 1
        assert result.price_snapshots[0].price_original == Decimal("15000.00")
        assert result.price_snapshots[0].price_sale == Decimal("12999.50")
