"""Ormatek scraper using undetected_chromedriver (Selenium-based).

Ormatek aggressively detects Playwright/Camoufox automation.
Only undetected_chromedriver (which patches Chrome CDP signatures) works.
Requires Python 3.11 (undetected_chromedriver not compatible with 3.13).

Run via: uv run --python 3.11 --with undetected-chromedriver --with selenium \
         --no-project python src/lineaf/scrapers/ormatek_uc.py
"""

import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
)
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("lineaf.scrapers.ormatek")

CATALOG_URL = "https://ormatek.com/catalog/matrasy/160x200/"

CHAR_LABEL_MAP = {
    "жесткость": "firmness",
    "высота": "height_cm",
    "наполнитель": "filler",
    "материал чехла": "cover_material",
    "max. вес на спальное место": "weight_kg",
    "максимальная нагрузка": "weight_kg",
}
# Note: on Ormatek product pages, firmness and filler are often NOT in
# characteristics-block — they appear as visual icons on catalog cards only.
# These fields will be NULL for most Ormatek products.


def init_driver():
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--start-maximized")
    return uc.Chrome(options=options, version_main=145)


def collect_product_urls(driver):
    """Collect all product URLs from catalog, clicking 'show more' until done."""
    driver.get(CATALOG_URL)
    time.sleep(5)

    # Click show more buttons
    while True:
        try:
            btn = None
            for sel in [
                "button.catalog-load-more",
                ".load-more button",
            ]:
                try:
                    btn = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    if btn:
                        break
                except TimeoutException:
                    continue

            if not btn:
                # Try XPath
                try:
                    btn = WebDriverWait(driver, 3).until(
                        EC.presence_of_element_located(
                            (By.XPATH, '//button[contains(.,"Показать ещё") or contains(.,"показать")]')
                        )
                    )
                except TimeoutException:
                    break

            if not btn:
                break

            driver.execute_script('arguments[0].scrollIntoView({block:"center"});', btn)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)

        except Exception:
            break

    # Collect URLs
    links = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/product/"]')
    unique = set()
    for l in links:
        href = l.get_attribute("href")
        if href:
            unique.add(href.split("?")[0])

    urls = sorted(unique)
    logger.info("ormatek: collected %d product URLs", len(urls))
    return urls


def parse_product(driver, url):
    """Parse a single product page."""
    driver.get(url)
    time.sleep(2)

    data = {
        "source_site": "ormatek",
        "source_url": url,
        "name": None,
        "firmness": None,
        "height_cm": None,
        "filler": None,
        "cover_material": None,
        "weight_kg": None,
        "price_sale": None,
        "price_original": None,
    }

    # Name
    try:
        title_el = driver.find_element(By.CSS_SELECTOR, "h1.detail-top-product-block__title")
        data["name"] = title_el.text.strip()
    except NoSuchElementException:
        try:
            data["name"] = driver.find_element(By.TAG_NAME, "h1").text.strip()
        except NoSuchElementException:
            pass

    # Prices
    try:
        price_el = driver.find_element(By.CSS_SELECTOR, "div.product-price-block__price")
        text = price_el.get_attribute("innerText").replace("\xa0", " ").strip()
        data["price_sale"] = _parse_price(text)
    except NoSuchElementException:
        pass

    try:
        old_el = driver.find_element(By.CSS_SELECTOR, "div.product-price-block__old-price")
        text = old_el.get_attribute("innerText").replace("\xa0", " ").strip()
        data["price_original"] = _parse_price(text)
    except NoSuchElementException:
        pass

    # Expand characteristics
    try:
        btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CLASS_NAME, "spoiler-block__btn"))
        )
        driver.execute_script("arguments[0].click();", btn)
        time.sleep(1)
    except (TimeoutException, Exception):
        pass

    # Characteristics
    try:
        props = driver.find_elements(By.CLASS_NAME, "characteristics-block__property")
        for p in props:
            try:
                name = p.find_element(By.CLASS_NAME, "characteristics-block__property-name").text.strip().lower()
                value = p.find_element(By.CLASS_NAME, "characteristics-block__property-value").text.strip()
                for key, field in CHAR_LABEL_MAP.items():
                    if key in name:
                        data[field] = value
                        break
            except NoSuchElementException:
                continue
    except Exception:
        pass

    # Firmness from features block
    try:
        feats = driver.find_elements(By.CLASS_NAME, "product-features-block__feature")
        for f in feats:
            try:
                nm = f.find_element(By.CLASS_NAME, "product-features-block__name").text.strip().lower()
                if "жесткость" in nm:
                    data["firmness"] = f.find_element(
                        By.CLASS_NAME, "product-features-block__value"
                    ).text.strip()
            except NoSuchElementException:
                continue
    except Exception:
        pass

    return data


def _parse_price(text):
    """Extract numeric price from text like '9 990 ₽'."""
    digits = re.sub(r"[^\d]", "", text)
    if digits:
        return Decimal(digits)
    return None


def run_scraper():
    """Main entry point — collect URLs, parse products, save to DB."""
    # Import DB models (needs PYTHONPATH or installed package)
    sys.path.insert(0, "src")
    from lineaf.database import SessionLocal
    from lineaf.models.product import Product
    from lineaf.models.price_snapshot import PriceSnapshot
    from lineaf.models.scrape_run import ScrapeRun
    from lineaf.scrapers.pipeline import upsert_product, insert_price_snapshot, mark_removed_products

    db = SessionLocal()
    scrape_run = ScrapeRun(
        site="ormatek",
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(scrape_run)
    db.commit()

    driver = init_driver()
    products_found = 0
    products_new = 0
    scraped_urls = set()

    try:
        urls = collect_product_urls(driver)

        for i, url in enumerate(urls, 1):
            try:
                data = parse_product(driver, url)

                if not data.get("name") or not data.get("price_sale"):
                    logger.warning("ormatek: skipping %s (no name or price)", url)
                    continue

                price_original = data.pop("price_original", None)
                price_sale = data.pop("price_sale", None)

                existing = (
                    db.query(Product)
                    .filter_by(source_site="ormatek", source_url=url)
                    .first()
                )

                product_id = upsert_product(db, data)

                if existing is None:
                    products_new += 1

                insert_price_snapshot(
                    db,
                    product_id=product_id,
                    scrape_run_id=scrape_run.id,
                    price_original=price_original,
                    price_sale=price_sale,
                )

                scraped_urls.add(url)
                products_found += 1
                db.commit()

                if i % 10 == 0:
                    logger.info("ormatek: processed %d/%d", i, len(urls))

            except Exception as e:
                logger.error("ormatek: error on %s: %s", url, e)
                db.rollback()
                continue

        # Mark removed
        products_removed = 0
        if products_found > 0:
            products_removed = mark_removed_products(db, "ormatek", scraped_urls)
            db.commit()

        scrape_run.status = "success"
        scrape_run.products_found = products_found
        scrape_run.products_new = products_new
        scrape_run.products_removed = products_removed
        scrape_run.finished_at = datetime.now(timezone.utc)
        db.commit()

        logger.info(
            "ormatek: complete — found=%d, new=%d, removed=%d",
            products_found, products_new, products_removed,
        )

    except Exception as e:
        logger.error("ormatek: failed: %s", e)
        scrape_run.status = "failed"
        scrape_run.error_message = str(e)[:2048]
        scrape_run.finished_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        driver.quit()
        db.close()


if __name__ == "__main__":
    run_scraper()
