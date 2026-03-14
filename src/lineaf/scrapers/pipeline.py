"""Item pipeline: UPSERT products, insert price snapshots, detect removed products."""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from lineaf.models.price_snapshot import PriceSnapshot
from lineaf.models.product import Product


def upsert_product(session: Session, data: dict) -> int:
    """Insert or update a product by (source_site, source_url).

    On conflict: updates name, attribute columns, and sets is_active=True
    (re-activating previously removed products).
    Returns the product id.

    Uses dialect-aware strategy:
    - PostgreSQL: INSERT ... ON CONFLICT DO UPDATE (atomic)
    - SQLite/other: SELECT then INSERT or UPDATE (fallback)
    """
    source_site = data["source_site"]
    source_url = data["source_url"]

    update_fields = {
        "name": data["name"],
        "firmness": data.get("firmness"),
        "height_cm": data.get("height_cm"),
        "filler": data.get("filler"),
        "cover_material": data.get("cover_material"),
        "weight_kg": data.get("weight_kg"),
        "is_active": True,
    }

    dialect_name = session.bind.dialect.name if session.bind else "unknown"

    if dialect_name == "postgresql":
        _upsert_pg(session, data, update_fields)
    else:
        _upsert_fallback(session, source_site, source_url, data, update_fields)

    session.flush()

    product = (
        session.query(Product)
        .filter_by(source_site=source_site, source_url=source_url)
        .one()
    )
    return product.id


def _upsert_pg(session: Session, data: dict, update_fields: dict) -> None:
    """PostgreSQL atomic UPSERT via INSERT ... ON CONFLICT DO UPDATE."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    insert_data = {
        "source_site": data["source_site"],
        "source_url": data["source_url"],
        **update_fields,
    }

    stmt = pg_insert(Product).values(**insert_data)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_products_site_url",
        set_=update_fields,
    )
    session.execute(stmt)


def _upsert_fallback(
    session: Session,
    source_site: str,
    source_url: str,
    data: dict,
    update_fields: dict,
) -> None:
    """Fallback UPSERT for SQLite and other dialects: SELECT then INSERT or UPDATE."""
    existing = (
        session.query(Product)
        .filter_by(source_site=source_site, source_url=source_url)
        .first()
    )

    if existing:
        for key, value in update_fields.items():
            setattr(existing, key, value)
    else:
        product = Product(
            source_site=source_site,
            source_url=source_url,
            **update_fields,
        )
        session.add(product)


def insert_price_snapshot(
    session: Session,
    product_id: int,
    scrape_run_id: int,
    price_original: Optional[Decimal] = None,
    price_sale: Optional[Decimal] = None,
) -> None:
    """Create a PriceSnapshot row linked to a product and scrape run."""
    snapshot = PriceSnapshot(
        product_id=product_id,
        scrape_run_id=scrape_run_id,
        price_original=price_original,
        price_sale=price_sale,
    )
    session.add(snapshot)
    session.flush()


def mark_removed_products(
    session: Session,
    source_site: str,
    scraped_urls: set[str],
) -> int:
    """Mark products as inactive if their URL was not in the current scrape.

    0-result guard: if scraped_urls is empty, returns 0 without changes.
    This prevents mass deactivation when a scrape fails to find any products.
    """
    if not scraped_urls:
        return 0

    count = (
        session.query(Product)
        .filter(
            Product.source_site == source_site,
            Product.is_active == True,  # noqa: E712
            Product.source_url.notin_(scraped_urls),
        )
        .update({"is_active": False}, synchronize_session=False)
    )
    session.flush()
    return count
