"""Price API endpoints: current prices, history, index, and Excel export."""

from __future__ import annotations

from io import BytesIO
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from lineaf.database import get_db
from lineaf.models.price_snapshot import PriceSnapshot
from lineaf.models.product import Product

router = APIRouter()


def _latest_snapshots_query(db: Session, site: Optional[str] = None):
    """Build query for latest PriceSnapshot per active Product.

    Returns list of (Product, PriceSnapshot) tuples for the most recent
    snapshot of each active product, optionally filtered by site.
    """
    # Subquery: max snapshot id per product (most recent)
    latest_sq = (
        db.query(
            PriceSnapshot.product_id,
            func.max(PriceSnapshot.id).label("max_snap_id"),
        )
        .group_by(PriceSnapshot.product_id)
        .subquery()
    )

    q = (
        db.query(Product, PriceSnapshot)
        .join(latest_sq, Product.id == latest_sq.c.product_id)
        .join(PriceSnapshot, PriceSnapshot.id == latest_sq.c.max_snap_id)
        .filter(Product.is_active.is_(True))
    )

    if site:
        q = q.filter(Product.source_site == site)

    return q.all()


def _row_to_dict(product: Product, snap: PriceSnapshot) -> dict:
    return {
        "product_id": product.id,
        "name": product.name,
        "source_site": product.source_site,
        "price_sale": float(snap.price_sale) if snap.price_sale is not None else None,
        "price_original": float(snap.price_original) if snap.price_original is not None else None,
        "scraped_at": snap.scraped_at.isoformat() if snap.scraped_at else None,
    }


@router.get("/dates")
def get_available_dates(db: Session = Depends(get_db)):
    """Return distinct scraped_at dates (date part only), newest first."""
    rows = (
        db.query(func.distinct(func.date(PriceSnapshot.scraped_at)).label("d"))
        .order_by(func.date(PriceSnapshot.scraped_at).desc())
        .all()
    )
    return [str(r.d) for r in rows if r.d is not None]


@router.get("/prices")
def get_prices(
    site: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Return latest price snapshot per active product, optionally filtered by site."""
    rows = _latest_snapshots_query(db, site=site)
    return [_row_to_dict(p, s) for p, s in rows]


@router.get("/products/all")
def get_all_products(db: Session = Depends(get_db)):
    """Return all products (active + inactive) with their site info."""
    products = db.query(Product).all()
    return [
        {
            "product_id": p.id,
            "name": p.name,
            "source_site": p.source_site,
            "is_active": p.is_active,
        }
        for p in products
    ]


@router.get("/prices/history")
def get_price_history(
    product_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Return all price snapshots for a product ordered by scraped_at asc."""
    snaps = (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.product_id == product_id)
        .order_by(PriceSnapshot.scraped_at.asc())
        .all()
    )
    return [
        {
            "scraped_at": s.scraped_at.isoformat() if s.scraped_at else None,
            "price_sale": float(s.price_sale) if s.price_sale is not None else None,
            "price_original": float(s.price_original) if s.price_original is not None else None,
        }
        for s in snaps
    ]


@router.get("/prices/index")
def get_price_index(db: Session = Depends(get_db)):
    """Return average price_sale per source_site (latest snapshot per product)."""
    latest_sq = (
        db.query(
            PriceSnapshot.product_id,
            func.max(PriceSnapshot.id).label("max_snap_id"),
        )
        .group_by(PriceSnapshot.product_id)
        .subquery()
    )

    rows = (
        db.query(
            Product.source_site,
            func.avg(PriceSnapshot.price_sale).label("avg_sale"),
        )
        .join(latest_sq, Product.id == latest_sq.c.product_id)
        .join(PriceSnapshot, PriceSnapshot.id == latest_sq.c.max_snap_id)
        .filter(Product.is_active.is_(True))
        .group_by(Product.source_site)
        .all()
    )

    return [
        {
            "site": row.source_site,
            "avg_price_sale": float(row.avg_sale) if row.avg_sale is not None else None,
        }
        for row in rows
    ]


@router.get("/products/details")
def get_product_details(
    site: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Return full product details including characteristics."""
    rows = _latest_snapshots_query(db, site=site)
    result = []
    for p, s in rows:
        result.append({
            "product_id": p.id,
            "name": p.name,
            "source_site": p.source_site,
            "price_sale": float(s.price_sale) if s.price_sale is not None else None,
            "price_original": float(s.price_original) if s.price_original is not None else None,
            "firmness": p.firmness,
            "height_cm": p.height_cm,
            "filler": p.filler,
            "cover_material": p.cover_material,
            "weight_kg": p.weight_kg,
            "source_url": p.source_url,
            "scraped_at": s.scraped_at.isoformat() if s.scraped_at else None,
        })
    return result


@router.get("/export")
def export_excel(db: Session = Depends(get_db)):
    """Export latest prices as an Excel file."""
    rows = _latest_snapshots_query(db)
    data = [_row_to_dict(p, s) for p, s in rows]

    df = pd.DataFrame(data)
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=prices.xlsx",
        },
    )
