"""CLI entry point for running scrapers sequentially."""

from __future__ import annotations

import argparse
import asyncio
import logging
import subprocess
import sys

logger = logging.getLogger("lineaf.scrapers")

# Registry of available spider classes (lazy imports to avoid circular deps)
SPIDER_REGISTRY: dict[str, str] = {
    "askona": "lineaf.scrapers.askona.AskonaScraper",
    "ormatek": "lineaf.scrapers.ormatek.OrmatemScraper",
    "sonum": "lineaf.scrapers.sonum.SonumScraper",
}

ALL_SITES = list(SPIDER_REGISTRY.keys())


def _import_spider(site: str):
    """Dynamically import and instantiate a spider class by site name."""
    module_path, class_name = SPIDER_REGISTRY[site].rsplit(".", 1)
    import importlib

    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def main(sites: list[str] | None = None) -> None:
    """Run scrapers for specified sites sequentially.

    Args:
        sites: List of site names to scrape. If None, runs all three.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    if sites is None:
        sites = ALL_SITES

    for site in sites:
        if site not in SPIDER_REGISTRY:
            logger.error("Unknown site: %s (available: %s)", site, ", ".join(ALL_SITES))
            continue

        logger.info("Starting scraper for %s", site)
        try:
            if site == "ormatek":
                # Ormatek requires undetected_chromedriver (Python 3.11)
                # because the site detects Playwright/Camoufox automation
                logger.info("ormatek: launching via undetected_chromedriver (Python 3.11)")
                import shutil
                uv_bin = shutil.which("uv") or str(__import__("pathlib").Path.home() / ".local/bin/uv")
                result = subprocess.run(
                    [
                        uv_bin, "run", "--python", "3.11",
                        "--with", "undetected-chromedriver",
                        "--with", "selenium",
                        "--with", "sqlalchemy",
                        "--with", "psycopg2-binary",
                        "--with", "pydantic-settings",
                        "--with", "python-dotenv",
                        "--no-project",
                        "python", "src/lineaf/scrapers/ormatek_uc.py",
                    ],
                    cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
                    capture_output=False,
                    timeout=600,
                )
                if result.returncode != 0:
                    logger.error("ormatek: subprocess exited with code %d", result.returncode)
            else:
                spider_cls = _import_spider(site)
                spider = spider_cls()
                asyncio.run(spider.run())
            logger.info("Completed scraper for %s", site)
        except Exception as e:
            logger.error("Scraper for %s failed: %s", site, e, exc_info=True)
            # Continue to next site — one failure should not stop others


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Lineaf price scrapers")
    parser.add_argument(
        "--sites",
        nargs="+",
        choices=ALL_SITES,
        default=None,
        help="Sites to scrape (default: all)",
    )
    args = parser.parse_args()
    main(sites=args.sites)
