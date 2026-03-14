"""RED phase: Tests that model classes exist and Base.metadata contains expected tables."""

from lineaf.models.base import Base


def test_product_model_exists():
    from lineaf.models.product import Product

    assert hasattr(Product, "__tablename__")
    assert Product.__tablename__ == "products"


def test_price_snapshot_model_exists():
    from lineaf.models.price_snapshot import PriceSnapshot

    assert hasattr(PriceSnapshot, "__tablename__")
    assert PriceSnapshot.__tablename__ == "price_snapshots"


def test_scrape_run_model_exists():
    from lineaf.models.scrape_run import ScrapeRun

    assert hasattr(ScrapeRun, "__tablename__")
    assert ScrapeRun.__tablename__ == "scrape_runs"


def test_all_tables_in_metadata():
    # Force registration by importing all models
    from lineaf.models import Product, PriceSnapshot, ScrapeRun  # noqa: F401

    tables = Base.metadata.tables
    assert "products" in tables
    assert "price_snapshots" in tables
    assert "scrape_runs" in tables


def test_product_has_unique_constraint():
    from lineaf.models.product import Product  # noqa: F811

    table = Product.__table__
    constraint_names = [c.name for c in table.constraints if hasattr(c, "name")]
    assert "uq_products_site_url" in constraint_names


def test_price_snapshot_uses_numeric():
    from lineaf.models.price_snapshot import PriceSnapshot  # noqa: F811
    import sqlalchemy

    table = PriceSnapshot.__table__
    col_orig = table.c.price_original
    col_sale = table.c.price_sale
    assert isinstance(col_orig.type, sqlalchemy.Numeric)
    assert isinstance(col_sale.type, sqlalchemy.Numeric)
    assert col_orig.type.precision == 12
    assert col_orig.type.scale == 2


def test_product_is_active_default():
    from lineaf.models.product import Product  # noqa: F811

    table = Product.__table__
    col = table.c.is_active
    assert col.default is not None or col.server_default is not None
