"""Product model — one row per unique mattress on a competitor site."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lineaf.models.base import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("source_site", "source_url", name="uq_products_site_url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_site: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)

    # Attribute columns (nullable)
    firmness: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    height_cm: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    filler: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    cover_material: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    weight_kg: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Timestamps
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    price_snapshots: Mapped[list["PriceSnapshot"]] = relationship(  # noqa: F821
        back_populates="product", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, site={self.source_site}, name={self.name!r})>"
