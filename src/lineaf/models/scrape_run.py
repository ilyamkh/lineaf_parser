"""ScrapeRun model — one row per spider execution."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from lineaf.models.base import Base


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    site: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="running"
    )

    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Counters
    products_found: Mapped[Optional[int]] = mapped_column(nullable=True)
    products_new: Mapped[Optional[int]] = mapped_column(nullable=True)
    products_removed: Mapped[Optional[int]] = mapped_column(nullable=True)

    # Error details
    error_message: Mapped[Optional[str]] = mapped_column(
        String(2048), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<ScrapeRun(id={self.id}, site={self.site}, status={self.status})>"
        )
