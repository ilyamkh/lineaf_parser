"""AskonaScraper: scrape 160x200 mattresses from askona.ru via __NEXT_DATA__ JSON."""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal
from html import unescape

from lineaf.scrapers.base import BaseScraper

logger = logging.getLogger("lineaf.scrapers.askona")

# Regex to extract __NEXT_DATA__ JSON from page HTML
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)

# Strip HTML tags from characteristic values (Askona wraps them in <a> tags)
_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Russian field name mapping for product characteristics
_FIELD_MAP = {
    "firmness": ["Жесткость"],
    "height_cm": ["Высота матраса"],
    "filler": ["Наполнитель"],
    "cover_material": ["Материал чехла", "Съемный чехол"],
    "weight_kg": ["Вес на спальное место, кг", "Вес матраса"],
}


def parse_askona_catalog_json(data: dict) -> list[str]:
    """Extract product URLs from a catalog page's __NEXT_DATA__ JSON.

    Filters items by type == "p" (products only, not banners).
    Returns absolute URLs with SELECTED_HASH_SIZE parameter preserved.
    """
    items = data["props"]["pageProps"]["data"]["listing"]["items"]
    base = "https://www.askona.ru"
    urls = []
    for item in items:
        if item.get("type") != "p":
            continue
        product_link = item.get("data", {}).get("productLink")
        if product_link:
            urls.append(base + product_link)
    return urls


def parse_askona_product_json(data: dict, url: str) -> dict:
    """Extract product fields from a detail page's __NEXT_DATA__ JSON.

    Returns dict with source_site, source_url, name, firmness, height_cm,
    filler, cover_material, weight_kg, price_sale, price_original.
    All optional fields default to None if not found.
    """
    pd = data["props"]["pageProps"]["productData"]

    # Build characteristics lookup from first characteristics group
    chars_groups = pd.get("characteristics", [])
    chars: dict[str, str] = {}
    if chars_groups and isinstance(chars_groups, list) and len(chars_groups) > 0:
        first_group = chars_groups[0]
        if isinstance(first_group, dict):
            for item in first_group.get("items", []):
                raw_value = item["value"]
                # Strip HTML tags (Askona wraps values in <a> links)
                clean_value = unescape(_HTML_TAG_RE.sub("", raw_value)).strip()
                chars[item["name"]] = clean_value

    # Map Russian field names to DB fields
    mapped: dict[str, str | None] = {}
    for db_field, ru_keys in _FIELD_MAP.items():
        value = None
        for key in ru_keys:
            if key in chars:
                value = chars[key]
                break
        mapped[db_field] = value

    # Extract prices (integers in JSON -> Decimal)
    price_raw = pd.get("price")
    old_price_raw = pd.get("oldPrice")
    price_sale = Decimal(str(price_raw)) if price_raw else None
    price_original = Decimal(str(old_price_raw)) if old_price_raw else None

    return {
        "source_site": "askona",
        "source_url": url,
        "name": pd.get("name", ""),
        **mapped,
        "price_sale": price_sale,
        "price_original": price_original,
    }


def _extract_next_data(content: str) -> dict | None:
    """Extract and parse __NEXT_DATA__ JSON from page HTML. Returns None on failure."""
    match = _NEXT_DATA_RE.search(content)
    if not match:
        return None
    return json.loads(match.group(1))


class AskonaScraper(BaseScraper):
    """Scraper for askona.ru 160x200 mattresses.

    Uses __NEXT_DATA__ JSON embedded in SSR pages for data extraction.
    Catalog pagination via ?page=N query parameter.
    """

    def __init__(self) -> None:
        super().__init__(
            site_name="askona",
            catalog_url="https://www.askona.ru/matrasy/160x200/",
        )

    async def collect_product_urls(self, page) -> list[str]:
        """Iterate catalog pages, extract product URLs from __NEXT_DATA__ JSON."""
        all_urls: list[str] = []
        page_num = 1

        while True:
            url = f"{self.catalog_url}?page={page_num}"
            await self.goto_with_retry(page, url)

            content = await page.content()
            data = _extract_next_data(content)

            if data is None:
                logger.warning(
                    "askona: __NEXT_DATA__ not found on catalog page %d, stopping pagination",
                    page_num,
                )
                break

            try:
                urls = parse_askona_catalog_json(data)
            except (KeyError, TypeError) as e:
                logger.warning(
                    "askona: failed to parse catalog JSON on page %d: %s",
                    page_num,
                    e,
                )
                break

            if not urls:
                logger.info(
                    "askona: no product URLs on page %d, pagination complete",
                    page_num,
                )
                break

            all_urls.extend(urls)
            logger.info(
                "askona: page %d yielded %d product URLs (total: %d)",
                page_num,
                len(urls),
                len(all_urls),
            )

            page_num += 1
            await self.delay()

        return all_urls

    async def extract_product(self, page, url: str) -> dict:
        """Extract product data from a detail page's __NEXT_DATA__ JSON."""
        content = await page.content()
        data = _extract_next_data(content)

        if data is None:
            logger.warning("askona: __NEXT_DATA__ not found on product page: %s", url)
            return {
                "source_site": "askona",
                "source_url": url,
                "name": "",
                "price_sale": None,
                "price_original": None,
            }

        try:
            result = parse_askona_product_json(data, url)
        except (KeyError, TypeError) as e:
            logger.warning(
                "askona: failed to parse product JSON for %s: %s", url, e
            )
            # Attempt minimal extraction
            pd = data.get("props", {}).get("pageProps", {}).get("productData", {})
            price_raw = pd.get("price")
            old_price_raw = pd.get("oldPrice")
            result = {
                "source_site": "askona",
                "source_url": url,
                "name": pd.get("name", ""),
                "firmness": None,
                "height_cm": None,
                "filler": None,
                "cover_material": None,
                "weight_kg": None,
                "price_sale": Decimal(str(price_raw)) if price_raw else None,
                "price_original": Decimal(str(old_price_raw)) if old_price_raw else None,
            }

        await self.delay()
        return result
