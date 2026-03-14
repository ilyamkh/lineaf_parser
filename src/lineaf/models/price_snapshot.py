"""PriceSnapshot model — one row per price observation of a product."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lineaf.models.base import Base


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    scrape_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("scrape_runs.id"), nullable=True
    )

    # Prices stored as NUMERIC(12,2) — never float
    price_original: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    price_sale: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )

    # Relationships
    product: Mapped["Product"] = relationship(  # noqa: F821
        back_populates="price_snapshots"
    )

    def __repr__(self) -> str:
        return (
            f"<PriceSnapshot(id={self.id}, product_id={self.product_id}, "
            f"original={self.price_original}, sale={self.price_sale})>"
        )
