"""OrmatemScraper: scrape 160x200 mattresses from ormatek.com via Camoufox.

Discovery notes (2026-03-14):
- ormatek.com returns 403 to ALL clients from this IP range (datacenter IP blocked).
- Even Camoufox headless=True, headless=False, and headless='virtual' (Linux only) all get 403.
- The 403 is at the server/CDN level (IP-based), not JavaScript-based protection.
- Site technology: Nuxt.js / Vue.js SSR (detected via Wappalyzer/search).
- Selectors below are BEST-GUESS based on typical Nuxt.js e-commerce patterns.
- TODO: Re-run discovery from a residential IP to verify selectors and pagination.

Catalog URL: https://www.ormatek.com/catalog/matrasy/160x200/
Pagination: Likely ?page=N (Nuxt.js convention) or ?PAGEN_1=N (Bitrix hybrid).
Product data: Likely in window.__NUXT__ SSR payload or rendered HTML.
"""

from __future__ import annotations

import json
import logging
import re

from lineaf.scrapers.base import BaseScraper
from lineaf.scrapers.utils import parse_price

logger = logging.getLogger("lineaf.scrapers.ormatek")

# Russian field name mapping for Ormatek product characteristics
# Based on standard Russian mattress field naming (same as Askona/Sonum)
CHAR_LABEL_MAP: dict[str, str] = {
    "Жесткость": "firmness",
    "Жёсткость": "firmness",
    "Уровень жесткости": "firmness",
    "Высота": "height_cm",
    "Высота матраса": "height_cm",
    "Наполнитель": "filler",
    "Материал чехла": "cover_material",
    "Чехол": "cover_material",
    "Вес": "weight_kg",
    "Вес на спальное место": "weight_kg",
    "Вес на 1 место": "weight_kg",
}


def parse_characteristics(rows: list[tuple[str, str]]) -> dict:
    """Map Russian label-value pairs from characteristics to DB field names.

    Args:
        rows: List of (label, value) tuples from the characteristics table/list.

    Returns:
        Dict with mapped field names. Only includes fields with known label mapping.
    """
    result: dict[str, str] = {}
    for label, value in rows:
        label_stripped = label.strip()
        value_stripped = value.strip()
        if label_stripped in CHAR_LABEL_MAP and value_stripped:
            field = CHAR_LABEL_MAP[label_stripped]
            # First match wins (more specific label takes priority)
            if field not in result:
                result[field] = value_stripped
    return result


def _try_extract_nuxt_data(content: str) -> dict | None:
    """Attempt to extract __NUXT__ or __NUXT_DATA__ from page HTML.

    Ormatek uses Nuxt.js; SSR data may be in:
    - window.__NUXT__ (Nuxt 2 pattern)
    - <script id="__NUXT_DATA__"> (Nuxt 3 pattern)
    - Inline <script> with __NUXT_DATA__ assignment

    Returns parsed JSON dict or None.
    """
    # Try Nuxt 3 pattern: <script type="application/json" id="__NUXT_DATA__">
    match = re.search(
        r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>',
        content,
        re.DOTALL,
    )
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    # Try Nuxt 2 pattern: window.__NUXT__ = {...}
    match = re.search(
        r"window\.__NUXT__\s*=\s*(\{.*?\})\s*;?\s*</script>",
        content,
        re.DOTALL,
    )
    if match:
        try:
            return json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    return None


class OrmatemScraper(BaseScraper):
    """Scraper for ormatek.com 160x200 mattresses.

    NOTE: ormatek.com returns 403 from datacenter IPs. This spider requires
    a residential IP or VPN to function. Selectors are best-guess based on
    Nuxt.js conventions and will need verification once access is available.

    Extraction strategy (in order of preference):
    1. __NUXT__ / __NUXT_DATA__ SSR payload (structured JSON)
    2. CSS selectors on rendered HTML (fallback)
    """

    def __init__(self) -> None:
        super().__init__(
            site_name="ormatek",
            catalog_url="https://www.ormatek.com/catalog/matrasy/160x200/",
        )

    async def collect_product_urls(self, page) -> list[str]:
        """Iterate catalog pages, extract product URLs.

        Tries multiple strategies:
        1. Extract from __NUXT__ SSR data if available
        2. CSS selectors for product card links
        Pagination via ?page=N (Nuxt.js convention).
        """
        all_urls: list[str] = []
        seen: set[str] = set()
        page_num = 1

        # CSS selectors for product card links (best-guess for Nuxt.js e-commerce)
        # Ordered by specificity: most likely first
        card_selectors = [
            'a[href*="/catalog/matrasy/"][href*=".htm"]',
            'a[href*="/catalog/matrasy/"][href*="/"]',
            ".product-card a[href]",
            ".catalog-item a[href]",
            ".product-item a[href]",
            '[class*="product"] a[href]',
            '[class*="catalog"] a[href*="matras"]',
        ]

        while True:
            url = f"{self.catalog_url}?page={page_num}"
            await self.goto_with_retry(page, url)

            # Strategy 1: Try __NUXT__ data
            content = await page.content()
            nuxt_data = _try_extract_nuxt_data(content)

            page_urls: list[str] = []

            if nuxt_data is not None:
                # Try to find product URLs in Nuxt data (structure unknown, best-guess)
                page_urls = self._extract_urls_from_nuxt(nuxt_data)
                if page_urls:
                    logger.info(
                        "ormatek: page %d — extracted %d URLs from __NUXT__ data",
                        page_num,
                        len(page_urls),
                    )

            # Strategy 2: CSS selectors fallback
            if not page_urls:
                for selector in card_selectors:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        for el in elements:
                            href = await el.get_attribute("href")
                            if href:
                                if href.startswith("/"):
                                    href = f"https://www.ormatek.com{href}"
                                page_urls.append(href)
                        if page_urls:
                            logger.info(
                                "ormatek: page %d — found %d links via selector '%s'",
                                page_num,
                                len(page_urls),
                                selector,
                            )
                            break

            if not page_urls:
                if page_num == 1:
                    # Log HTML snippet for debugging
                    logger.warning(
                        "ormatek: page 1 returned no product URLs. "
                        "This may be due to 403 blocking or wrong selectors. "
                        "HTML snippet: %s",
                        content[:500],
                    )
                else:
                    logger.info(
                        "ormatek: no products on page %d, pagination complete",
                        page_num,
                    )
                break

            # Deduplicate
            new_count = 0
            for u in page_urls:
                if u not in seen:
                    seen.add(u)
                    all_urls.append(u)
                    new_count += 1

            logger.info(
                "ormatek: page %d — %d new URLs (%d total)",
                page_num,
                new_count,
                len(all_urls),
            )

            page_num += 1
            await self.delay()

        return all_urls

    def _extract_urls_from_nuxt(self, data: dict) -> list[str]:
        """Best-guess extraction of product URLs from __NUXT__ data.

        Nuxt SSR data structure varies by app. Common patterns:
        - data.fetch.products[].url
        - data[0].products[].slug
        - state.catalog.products[].link

        Returns list of absolute URLs found, or empty list.
        """
        urls: list[str] = []
        base = "https://www.ormatek.com"

        # Recursively search for product-like URL strings
        self._find_product_urls(data, urls, base, depth=0)

        return urls

    def _find_product_urls(
        self, obj, urls: list[str], base: str, depth: int
    ) -> None:
        """Recursively search JSON structure for product URLs."""
        if depth > 10:
            return

        if isinstance(obj, str):
            # Look for product-like URL patterns
            if "/catalog/matrasy/" in obj and obj != self.catalog_url:
                if obj.startswith("/"):
                    urls.append(base + obj)
                elif obj.startswith("http"):
                    urls.append(obj)
        elif isinstance(obj, dict):
            for value in obj.values():
                self._find_product_urls(value, urls, base, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                self._find_product_urls(item, urls, base, depth + 1)

    async def extract_product(self, page, url: str) -> dict:
        """Extract product data from an Ormatek product detail page.

        Tries:
        1. __NUXT__ data for structured product info
        2. CSS selectors on rendered HTML
        """
        # Name extraction
        name = None
        h1 = await page.query_selector("h1")
        if h1:
            name = await h1.inner_text()
            name = name.strip() if name else None
        if not name:
            name = await page.title()
            name = name.strip() if name else None

        # Price extraction
        price_sale = None
        price_original = None

        # Try __NUXT__ data first for prices
        content = await page.content()
        nuxt_data = _try_extract_nuxt_data(content)

        if nuxt_data is not None:
            prices = self._extract_prices_from_nuxt(nuxt_data)
            if prices:
                price_sale = prices.get("price_sale")
                price_original = prices.get("price_original")

        # Fallback: CSS selectors for prices
        if price_sale is None:
            price_selectors = [
                ".product-price",
                ".price-current",
                ".price__current",
                '[class*="price"]',
                ".price",
            ]
            price_texts: list[str] = []
            for selector in price_selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    for el in elements:
                        text = await el.inner_text()
                        if text and re.search(r"\d", text):
                            price_texts.append(text.strip())
                    if price_texts:
                        break

            # Parse collected price texts
            parsed_prices = []
            for text in price_texts:
                p = parse_price(text)
                if p is not None and p > 0:
                    parsed_prices.append(p)

            parsed_prices = sorted(set(parsed_prices))

            if len(parsed_prices) >= 2:
                price_sale = parsed_prices[0]
                price_original = parsed_prices[-1]
            elif len(parsed_prices) == 1:
                price_sale = parsed_prices[0]

        # Characteristics extraction
        # Try multiple table/list selectors for characteristics
        char_selectors = [
            ".product-chars tr",
            ".product-info tr",
            ".characteristics tr",
            ".specs tr",
            '[class*="character"] tr',
            '[class*="param"] tr',
            "table.params tr",
            "table tr",
        ]

        rows: list[tuple[str, str]] = []
        for selector in char_selectors:
            tr_elements = await page.query_selector_all(selector)
            if tr_elements:
                for tr in tr_elements:
                    cells = await tr.query_selector_all("td")
                    if len(cells) >= 2:
                        label = await cells[0].inner_text()
                        value = await cells[1].inner_text()
                        if label and value:
                            rows.append((label.strip(), value.strip()))
                    # Also try th + td pattern
                    if not cells:
                        th = await tr.query_selector("th")
                        td = await tr.query_selector("td")
                        if th and td:
                            label = await th.inner_text()
                            value = await td.inner_text()
                            if label and value:
                                rows.append((label.strip(), value.strip()))
                if rows:
                    break

        # Also try dl/dt/dd structure
        if not rows:
            dt_elements = await page.query_selector_all("dt")
            dd_elements = await page.query_selector_all("dd")
            if dt_elements and dd_elements:
                for dt, dd in zip(dt_elements, dd_elements):
                    label = await dt.inner_text()
                    value = await dd.inner_text()
                    if label and value:
                        rows.append((label.strip(), value.strip()))

        # Also try div-based key-value pairs (common in Vue/Nuxt apps)
        if not rows:
            kv_selectors = [
                '[class*="characteristic"] [class*="name"]',
                '[class*="param"] [class*="name"]',
                '[class*="spec"] [class*="name"]',
            ]
            for selector in kv_selectors:
                name_els = await page.query_selector_all(selector)
                if name_els:
                    for name_el in name_els:
                        label = await name_el.inner_text()
                        # Value is usually the next sibling or parent's other child
                        value_el = await name_el.evaluate_handle(
                            "el => el.nextElementSibling"
                        )
                        if value_el:
                            value = await value_el.inner_text()
                            if label and value:
                                rows.append((label.strip(), value.strip()))
                    if rows:
                        break

        chars = parse_characteristics(rows)

        if not rows:
            logger.info(
                "ormatek: no characteristics found for %s", url
            )

        await self.delay()

        return {
            "source_site": self.site_name,
            "source_url": url,
            "name": name,
            "firmness": chars.get("firmness"),
            "height_cm": chars.get("height_cm"),
            "filler": chars.get("filler"),
            "cover_material": chars.get("cover_material"),
            "weight_kg": chars.get("weight_kg"),
            "price_sale": price_sale,
            "price_original": price_original,
        }

    def _extract_prices_from_nuxt(self, data: dict) -> dict:
        """Best-guess extraction of prices from __NUXT__ data.

        Common Nuxt e-commerce patterns:
        - data.product.price / data.product.oldPrice
        - data.fetch.product.price / .basePrice

        Returns dict with price_sale and/or price_original keys.
        """
        from decimal import Decimal

        prices: dict = {}

        # Recursively find price-like fields
        price_fields = self._find_price_fields(data, depth=0)

        if price_fields:
            # Sort: lower is sale, higher is original
            numeric_prices = sorted(set(price_fields))
            if len(numeric_prices) >= 2:
                prices["price_sale"] = Decimal(str(numeric_prices[0]))
                prices["price_original"] = Decimal(str(numeric_prices[-1]))
            elif len(numeric_prices) == 1:
                prices["price_sale"] = Decimal(str(numeric_prices[0]))

        return prices

    def _find_price_fields(
        self, obj, depth: int, _key: str = ""
    ) -> list[int | float]:
        """Recursively find numeric values associated with price-like keys."""
        if depth > 8:
            return []

        results: list[int | float] = []

        price_keys = {"price", "oldPrice", "old_price", "basePrice", "salePrice",
                       "currentPrice", "regularPrice", "discountPrice"}

        if isinstance(obj, dict):
            for key, value in obj.items():
                if key.lower().replace("_", "") in {k.lower() for k in price_keys}:
                    if isinstance(value, (int, float)) and value > 0:
                        results.append(value)
                else:
                    results.extend(
                        self._find_price_fields(value, depth + 1, key)
                    )
        elif isinstance(obj, list):
            for item in obj:
                results.extend(
                    self._find_price_fields(item, depth + 1, _key)
                )

        return results
