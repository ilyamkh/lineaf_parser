"""Product API endpoints: new/removed product detection."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from lineaf.database import get_db
from lineaf.models.product import Product

router = APIRouter()


@router.get("/products/changes")
def get_product_changes(db: Session = Depends(get_db)):
    """Return recently new and removed products.

    - new: products with first_seen_at within the last 8 days and is_active=True
    - removed: products with is_active=False, ordered by updated_at desc, limit 50
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=8)

    new_products = (
        db.query(Product)
        .filter(Product.is_active.is_(True))
        .filter(Product.first_seen_at >= cutoff)
        .all()
    )

    removed_products = (
        db.query(Product)
        .filter(Product.is_active.is_(False))
        .order_by(Product.updated_at.desc())
        .limit(50)
        .all()
    )

    return {
        "new": [
            {"name": p.name, "source_site": p.source_site}
            for p in new_products
        ],
        "removed": [
            {"name": p.name, "source_site": p.source_site}
            for p in removed_products
        ],
    }
