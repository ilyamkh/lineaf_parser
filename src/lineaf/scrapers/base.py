"""BaseScraper: abstract base class with Camoufox browser, retry, delay, ScrapeRun lifecycle."""

from __future__ import annotations

import abc
import asyncio
import logging
import random
from datetime import datetime, timezone

from contextlib import asynccontextmanager

from camoufox.async_api import AsyncCamoufox
from playwright.async_api import async_playwright

from lineaf.database import SessionLocal
from lineaf.models.scrape_run import ScrapeRun
from lineaf.scrapers.pipeline import (
    insert_price_snapshot,
    mark_removed_products,
    upsert_product,
)
from lineaf.scrapers.utils import validate_product

logger = logging.getLogger("lineaf.scrapers")


class BaseScraper(abc.ABC):
    """Abstract base class for all site scrapers.

    Subclasses must implement:
        - collect_product_urls(page) -> list[str]
        - extract_product(page, url) -> dict
    """

    # Browser engine: "camoufox" (Firefox) or "chromium" (Playwright Chromium)
    browser_engine: str = "camoufox"

    def __init__(self, site_name: str, catalog_url: str) -> None:
        self.site_name = site_name
        self.catalog_url = catalog_url

    @asynccontextmanager
    async def _launch_browser(self):
        """Launch browser based on engine preference."""
        if self.browser_engine == "chromium":
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                page = await browser.new_page()
                try:
                    yield page
                finally:
                    await page.close()
                    await browser.close()
        else:
            async with AsyncCamoufox(headless=True) as browser:
                page = await browser.new_page()
                try:
                    yield page
                finally:
                    await page.close()

    async def run(self) -> None:
        """Orchestrate a full scrape run: browser -> collect -> extract -> pipeline."""
        db = SessionLocal()
        scrape_run = ScrapeRun(
            site=self.site_name,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        db.add(scrape_run)
        db.commit()

        products_found = 0
        products_new = 0
        products_removed = 0
        scraped_urls: set[str] = set()

        try:
            async with self._launch_browser() as page:
                # Stage 1: collect product URLs from catalog
                product_urls = await self.collect_product_urls(page)
                logger.info(
                    "%s: collected %d product URLs from catalog",
                    self.site_name,
                    len(product_urls),
                )

                # Stage 2: visit each product page and extract data
                for url in product_urls:
                    try:
                        await self.goto_with_retry(page, url)
                        await self.delay()

                        product_data = await self.extract_product(page, url)

                        if not validate_product(product_data):
                            logger.warning(
                                "%s: skipping invalid product (missing name or price): %s",
                                self.site_name,
                                url,
                            )
                            continue

                        # Extract prices before upsert (they are not Product columns)
                        price_original = product_data.pop("price_original", None)
                        price_sale = product_data.pop("price_sale", None)

                        # Check if product existed before upsert
                        from lineaf.models.product import Product

                        existing = (
                            db.query(Product)
                            .filter_by(
                                source_site=product_data["source_site"],
                                source_url=product_data["source_url"],
                            )
                            .first()
                        )

                        product_id = upsert_product(db, product_data)

                        if existing is None:
                            products_new += 1

                        insert_price_snapshot(
                            db,
                            product_id=product_id,
                            scrape_run_id=scrape_run.id,
                            price_original=price_original,
                            price_sale=price_sale,
                        )

                        scraped_urls.add(product_data["source_url"])
                        products_found += 1
                        db.commit()

                    except Exception as e:
                        logger.error(
                            "%s: error extracting product %s: %s",
                            self.site_name,
                            url,
                            e,
                        )
                        db.rollback()
                        continue

            # Mark removed products (only if we found at least 1)
            if products_found > 0:
                products_removed = mark_removed_products(
                    db, self.site_name, scraped_urls
                )
                db.commit()

            # Update scrape run as success
            scrape_run.status = "success"
            scrape_run.products_found = products_found
            scrape_run.products_new = products_new
            scrape_run.products_removed = products_removed
            scrape_run.finished_at = datetime.now(timezone.utc)
            db.commit()

            logger.info(
                "%s: scrape complete — found=%d, new=%d, removed=%d",
                self.site_name,
                products_found,
                products_new,
                products_removed,
            )

        except Exception as e:
            logger.error("%s: scrape run failed: %s", self.site_name, e)
            scrape_run.status = "failed"
            scrape_run.error_message = str(e)[:2048]
            scrape_run.finished_at = datetime.now(timezone.utc)
            db.commit()
            raise

        finally:
            db.close()

    async def goto_with_retry(
        self, page, url: str, max_attempts: int = 3
    ) -> None:
        """Navigate to URL with retry on 403/timeout/NS_ERROR_ABORT.

        Handles Firefox-specific NS_ERROR_ABORT (navigation aborted by
        competing client-side navigation, e.g. Next.js SPA routing or
        modal popups). When this error occurs, checks if the page actually
        loaded before retrying.

        Uses escalating strategy:
        1. Normal page.goto with domcontentloaded
        2. On NS_ERROR_ABORT: check if page loaded anyway, else retry
           with shorter wait (it's a browser conflict, not rate-limiting)
        3. Final fallback: JS-based navigation (window.location)
        """
        for attempt in range(max_attempts):
            try:
                response = await page.goto(
                    url, timeout=60000, wait_until="domcontentloaded"
                )
                if response and response.status == 403:
                    raise RuntimeError(f"403 Forbidden: {url}")
                return response
            except Exception as e:
                error_msg = str(e)
                is_abort = "NS_ERROR_ABORT" in error_msg or "NS_BINDING_ABORTED" in error_msg

                if is_abort:
                    # Firefox NS_ERROR_ABORT: page may have loaded despite the error.
                    # Check if the current page URL matches and has content.
                    try:
                        await asyncio.sleep(2)
                        current_url = page.url
                        content = await page.content()
                        # If we're on the right page and it has real content, treat as success
                        if len(content) > 1000:
                            logger.info(
                                "%s: NS_ERROR_ABORT on %s but page loaded (url=%s, len=%d), continuing",
                                self.site_name,
                                url,
                                current_url,
                                len(content),
                            )
                            return None
                    except Exception:
                        pass  # Page truly didn't load, fall through to retry

                if attempt == max_attempts - 1:
                    # Final attempt: try JS-based navigation as last resort
                    if is_abort:
                        try:
                            logger.info(
                                "%s: final attempt using JS navigation for %s",
                                self.site_name,
                                url,
                            )
                            await page.evaluate(f"window.location.href = {url!r}")
                            await page.wait_for_load_state(
                                "domcontentloaded", timeout=60000
                            )
                            return None
                        except Exception as e2:
                            logger.error(
                                "%s: JS navigation also failed for %s: %s",
                                self.site_name,
                                url,
                                e2,
                            )
                    raise

                # Short wait for abort errors (browser conflict, not rate-limit)
                # Longer wait for other errors (network, server issues)
                wait = random.uniform(3, 8) if is_abort else random.uniform(30, 60)
                logger.warning(
                    "%s: attempt %d/%d failed for %s (%s), retrying in %.0fs",
                    self.site_name,
                    attempt + 1,
                    max_attempts,
                    url,
                    e,
                    wait,
                )
                await asyncio.sleep(wait)

    async def delay(self) -> None:
        """Random delay between requests (2-5 seconds)."""
        await asyncio.sleep(random.uniform(2, 5))

    @abc.abstractmethod
    async def collect_product_urls(self, page) -> list[str]:
        """Collect all product URLs from the catalog pages."""
        ...

    @abc.abstractmethod
    async def extract_product(self, page, url: str) -> dict:
        """Extract product data from a single product page.

        Must return a dict with keys matching Product model columns
        plus 'price_original' and 'price_sale'.
        """
        ...
