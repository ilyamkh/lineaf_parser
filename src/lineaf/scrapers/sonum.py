"""SonumScraper: scrape 160x200 mattresses from sonum.ru using Bitrix PAGEN_1 pagination."""

from __future__ import annotations

import logging
import re

from lineaf.scrapers.base import BaseScraper
from lineaf.scrapers.utils import parse_price

logger = logging.getLogger("lineaf.scrapers")

# Russian label -> DB field mapping for characteristics table
CHAR_LABEL_MAP: dict[str, str] = {
    "Жесткость матраса": "firmness",
    "Жесткость": "firmness",
    "Высота матраса": "height_cm",
    "Высота": "height_cm",
    "Материал чехла": "cover_material",
    "Вес на 1 место": "weight_kg",
    "Вес": "weight_kg",
}

# Regex to extract filler from product description text
FILLER_RE = re.compile(r"[Нн]аполнитель[:\s]+([^.]+)")


def parse_characteristics(rows: list[tuple[str, str]]) -> dict:
    """Map Russian label-value pairs from characteristics table to DB field names.

    Args:
        rows: List of (label, value) tuples from the characteristics table.

    Returns:
        Dict with mapped field names (firmness, height_cm, cover_material, weight_kg).
        Only includes fields that have a known label mapping.
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


def extract_filler_from_description(text: str) -> str | None:
    """Extract filler material from product description text via regex.

    Looks for patterns like "Наполнитель: пена с эффектом памяти" in the text.

    Returns:
        Filler string if found, None otherwise.
    """
    if not text:
        return None
    match = FILLER_RE.search(text)
    if match:
        return match.group(1).strip()
    return None


class SonumScraper(BaseScraper):
    """Scraper for sonum.ru mattress catalog (160x200 size filter).

    Uses Bitrix CMS PAGEN_1 pagination parameter to iterate catalog pages.
    Extracts product data from server-rendered HTML using CSS selectors
    with multiple fallback strategies.
    """

    def __init__(self) -> None:
        super().__init__(
            site_name="sonum",
            catalog_url=(
                "https://www.sonum.ru/catalog/matrasy/"
                "?filter%5Bwidth%5D%5B0%5D=160&filter%5Blength%5D%5B0%5D=200"
            ),
        )

    async def collect_product_urls(self, page) -> list[str]:
        """Collect all product URLs from catalog pages using PAGEN_1 pagination.

        Iterates pages until a page returns 0 product cards.
        Deduplicates URLs across pages.
        """
        all_urls: list[str] = []
        seen: set[str] = set()
        page_num = 1

        # CSS selectors for product card links, tried in order
        card_selectors = [
            ".catalog-item a[href]",
            ".product-card a[href]",
            'a[href*="/catalog/matrasy/"]',
        ]

        while True:
            # Build paginated URL
            paginated_url = f"{self.catalog_url}&PAGEN_1={page_num}"
            await self.goto_with_retry(page, paginated_url)

            # Try each selector to find product links
            product_links = []
            for selector in card_selectors:
                elements = await page.query_selector_all(selector)
                if elements:
                    product_links = elements
                    break

            if not product_links:
                logger.info(
                    "%s: no product cards found on page %d, stopping pagination",
                    self.site_name,
                    page_num,
                )
                # Log page snippet for debugging if page 1 returns nothing
                if page_num == 1:
                    content = await page.content()
                    logger.warning(
                        "%s: page 1 returned no products. HTML snippet: %s",
                        self.site_name,
                        content[:500],
                    )
                break

            # Extract hrefs and build absolute URLs
            page_urls_count = 0
            for link in product_links:
                href = await link.get_attribute("href")
                if not href:
                    continue
                # Build absolute URL
                if href.startswith("/"):
                    href = f"https://www.sonum.ru{href}"
                # Deduplicate
                if href not in seen:
                    seen.add(href)
                    all_urls.append(href)
                    page_urls_count += 1

            logger.info(
                "%s: page %d — found %d new product URLs (%d total)",
                self.site_name,
                page_num,
                page_urls_count,
                len(all_urls),
            )

            page_num += 1
            await self.delay()

        return all_urls

    async def extract_product(self, page, url: str) -> dict:
        """Extract product data from a Sonum product detail page.

        Extracts name, prices, and characteristics from server-rendered HTML.
        Falls back to description text for filler field.
        """
        await self.goto_with_retry(page, url)

        # --- Name ---
        name = None
        h1 = await page.query_selector("h1")
        if h1:
            name = await h1.inner_text()
            name = name.strip() if name else None
        if not name:
            logger.warning("%s: h1 not found for %s, trying title", self.site_name, url)
            name = await page.title()
            name = name.strip() if name else None

        # --- Prices ---
        price_sale = None
        price_original = None

        # Try multiple selectors for price elements
        price_selectors = [
            ".product-price",
            ".price",
            "[class*='price']",
        ]
        price_texts: list[str] = []
        for selector in price_selectors:
            elements = await page.query_selector_all(selector)
            if elements:
                for el in elements:
                    text = await el.inner_text()
                    if text and ("₽" in text or re.search(r"\d", text)):
                        price_texts.append(text.strip())
                if price_texts:
                    break

        # If no price elements found via selectors, try scanning page for price-like text
        if not price_texts:
            # Look for any element containing the ruble sign
            rub_elements = await page.query_selector_all("span")
            for el in rub_elements:
                text = await el.inner_text()
                if text and "₽" in text:
                    price_texts.append(text.strip())

        # Parse collected price texts
        parsed_prices = []
        for text in price_texts:
            p = parse_price(text)
            if p is not None and p > 0:
                parsed_prices.append(p)

        # Deduplicate and sort
        parsed_prices = sorted(set(parsed_prices))

        if len(parsed_prices) >= 2:
            # Lower is sale, higher is original
            price_sale = parsed_prices[0]
            price_original = parsed_prices[-1]
        elif len(parsed_prices) == 1:
            price_sale = parsed_prices[0]
        else:
            logger.warning(
                "%s: no prices found for %s", self.site_name, url
            )

        # --- Characteristics table ---
        char_selectors = [
            ".product-chars table tr",
            ".product-info table tr",
            "table.chars tr",
            ".characteristics tr",
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

        chars = parse_characteristics(rows)

        if not rows:
            logger.info(
                "%s: no characteristics table found for %s",
                self.site_name,
                url,
            )

        # --- Filler fallback: try description text ---
        filler = chars.get("filler")
        if not filler:
            page_text = await page.inner_text("body")
            filler = extract_filler_from_description(page_text or "")

        await self.delay()

        return {
            "source_site": self.site_name,
            "source_url": url,
            "name": name,
            "firmness": chars.get("firmness"),
            "height_cm": chars.get("height_cm"),
            "filler": filler,
            "cover_material": chars.get("cover_material"),
            "weight_kg": chars.get("weight_kg"),
            "price_sale": price_sale,
            "price_original": price_original,
        }
