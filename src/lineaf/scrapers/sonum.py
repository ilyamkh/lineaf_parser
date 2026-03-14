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
    Extracts product data from server-rendered HTML using CSS selectors.
    """

    def __init__(self) -> None:
        super().__init__(
            site_name="sonum",
            catalog_url=(
                "https://www.sonum.ru/catalog/matrasy/"
                "?filter%5Bwidth%5D%5B0%5D=160&filter%5Blength%5D%5B0%5D=200"
            ),
        )
        self._city_dismissed = False

    async def _dismiss_city_modal(self, page) -> None:
        """Dismiss the 'Ваш город — Москва?' modal if present."""
        if self._city_dismissed:
            return
        try:
            confirm = await page.query_selector("a.modal-has-delete__delete")
            if confirm:
                text = await confirm.inner_text()
                if "да" in text.lower():
                    await confirm.click()
                    await page.wait_for_timeout(1000)
                    self._city_dismissed = True
                    logger.info("sonum: dismissed city modal")
        except Exception:
            pass

    async def collect_product_urls(self, page) -> list[str]:
        """Collect all product URLs from catalog pages using PAGEN_1 pagination.

        Iterates pages until a page returns 0 product cards.
        Deduplicates URLs across pages.
        """
        all_urls: list[str] = []
        seen: set[str] = set()
        page_num = 1
        empty_pages = 0  # consecutive pages with 0 new URLs

        # CSS selectors for product card links, tried in order
        # Use specific selectors from working notebook
        card_selectors = [
            "a.card-product__title",
            ".catalog-item a[href]",
            ".product-card a[href]",
        ]

        while True:
            # Build paginated URL
            paginated_url = f"{self.catalog_url}&PAGEN_1={page_num}"
            await self.goto_with_retry(page, paginated_url)
            await self._dismiss_city_modal(page)

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

            if page_urls_count == 0:
                empty_pages += 1
                if empty_pages >= 2:
                    logger.info(
                        "%s: %d consecutive empty pages, stopping pagination",
                        self.site_name,
                        empty_pages,
                    )
                    break
            else:
                empty_pages = 0

            page_num += 1
            await self.delay()

        return all_urls

    async def extract_product(self, page, url: str) -> dict:
        """Extract product data from a Sonum product detail page.

        Extracts name, prices, and characteristics from server-rendered HTML.
        Falls back to description text for filler field.
        """
        # Note: page navigation already done by BaseScraper.run()
        await self._dismiss_city_modal(page)

        # --- Name (from working notebook: h1.product-detail-card__title) ---
        name = None
        name_el = await page.query_selector("h1.product-detail-card__title")
        if not name_el:
            name_el = await page.query_selector("h1")
        if name_el:
            name = (await name_el.inner_text()).strip()

        # --- Prices (from working notebook: specific Sonum selectors) ---
        price_sale = None
        price_original = None

        # Current price
        sale_el = await page.query_selector(
            "div.product-detail-card__current-price span[class*='js-price-current']"
        )
        if sale_el:
            text = await sale_el.inner_text()
            price_sale = parse_price(text)

        # Old price
        old_el = await page.query_selector(
            "div.product-detail-card__old-price span[class*='js-old-price-current']"
        )
        if old_el:
            text = await old_el.inner_text()
            price_original = parse_price(text)

        # Fallback: scan for any price-like elements
        if price_sale is None:
            for selector in [".product-price", "[class*='price']"]:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    text = await el.inner_text()
                    p = parse_price(text)
                    if p and p > 0:
                        price_sale = p
                        break
                if price_sale:
                    break

        if not price_sale:
            logger.warning("%s: no prices found for %s", self.site_name, url)

        # --- Characteristics (from working notebook: div#characteristic) ---
        rows: list[tuple[str, str]] = []

        # Primary: Sonum's characteristic table
        char_rows = await page.query_selector_all(
            "div#characteristic div.table-characteristic__row"
        )
        if char_rows:
            for row_el in char_rows:
                cols = await row_el.query_selector_all("div.table-characteristic__col")
                if len(cols) >= 2:
                    label = await cols[0].inner_text()
                    value = await cols[1].inner_text()
                    if label and value:
                        rows.append((label.strip(), value.strip()))

        # Fallback: generic table
        if not rows:
            for selector in ["table tr", ".characteristics tr"]:
                tr_elements = await page.query_selector_all(selector)
                for tr in tr_elements:
                    cells = await tr.query_selector_all("td")
                    if len(cells) >= 2:
                        label = await cells[0].inner_text()
                        value = await cells[1].inner_text()
                        if label and value:
                            rows.append((label.strip(), value.strip()))
                if rows:
                    break

        chars = parse_characteristics(rows)

        if not rows:
            logger.info(
                "%s: no characteristics table found for %s",
                self.site_name,
                url,
            )

        # --- Height fallback: data-select-height attribute ---
        height = chars.get("height_cm")
        if not height:
            height_el = await page.query_selector("[data-select-height]")
            if height_el:
                height = await height_el.get_attribute("data-select-height")

        # --- Filler: try characteristics, then "Состав:" in page text ---
        filler = chars.get("filler")
        if not filler:
            page_text = await page.inner_text("body")
            # Try "Состав: ..." pattern first
            sostav_match = re.search(r"Состав:\s*(.+?)(?:\n|$)", page_text or "")
            if sostav_match:
                filler = sostav_match.group(1).strip()
            else:
                filler = extract_filler_from_description(page_text or "")

        # Note: delay is handled by BaseScraper.run() after each product

        return {
            "source_site": self.site_name,
            "source_url": url,
            "name": name,
            "firmness": chars.get("firmness"),
            "height_cm": height,
            "filler": filler,
            "cover_material": chars.get("cover_material"),
            "weight_kg": chars.get("weight_kg"),
            "price_sale": price_sale,
            "price_original": price_original,
        }
