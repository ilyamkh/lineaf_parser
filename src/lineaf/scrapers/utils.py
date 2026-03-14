"""Scraper utilities: price parsing and product validation."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


def parse_price(text: str | None) -> Decimal | None:
    """Extract numeric price from Russian formatted string like '25 180 rub'.

    Handles spaces, non-breaking spaces, currency symbols, 'rub.' suffix,
    and comma-as-decimal-separator (e.g. '12 345,67 rub.').
    Returns None for empty/None input or unparseable text.
    """
    if not text:
        return None
    # Replace comma with dot for decimal separator, then strip non-numeric chars
    cleaned = re.sub(r"[^\d,.]", "", text.replace(",", "."))
    # Remove trailing/leading dots (e.g. from "руб." suffix)
    cleaned = cleaned.strip(".")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def validate_product(data: dict) -> bool:
    """Return True if product has a non-empty name AND at least one price."""
    name = data.get("name")
    if not name or not str(name).strip():
        return False
    has_price = (
        data.get("price_sale") is not None or data.get("price_original") is not None
    )
    return has_price
