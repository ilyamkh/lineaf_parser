"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-14

Creates products, scrape_runs, and price_snapshots tables.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- products --
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_site", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("firmness", sa.String(length=256), nullable=True),
        sa.Column("height_cm", sa.String(length=64), nullable=True),
        sa.Column("filler", sa.String(length=512), nullable=True),
        sa.Column("cover_material", sa.String(length=256), nullable=True),
        sa.Column("weight_kg", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_site", "source_url", name="uq_products_site_url"),
    )

    # -- scrape_runs (must be created before price_snapshots due to FK) --
    op.create_table(
        "scrape_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("site", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("products_found", sa.Integer(), nullable=True),
        sa.Column("products_new", sa.Integer(), nullable=True),
        sa.Column("products_removed", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=2048), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # -- price_snapshots --
    op.create_table(
        "price_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("scrape_run_id", sa.Integer(), nullable=True),
        sa.Column("price_original", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("price_sale", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["scrape_run_id"], ["scrape_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("price_snapshots")
    op.drop_table("scrape_runs")
    op.drop_table("products")
