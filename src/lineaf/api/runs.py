"""Scrape run API endpoints: run log, freshness, and manual trigger."""

from __future__ import annotations

import threading

from fastapi import APIRouter

from lineaf.run_scrapers import main as run_scrapers_main

router = APIRouter()


@router.post("/scrape")
async def trigger_scrape():
    """Start scrapers in a background daemon thread and return immediately.

    Uses a daemon thread (not FastAPI BackgroundTasks) because scraper runs
    take 10+ minutes and would exhaust the ASGI worker thread pool.
    """
    threading.Thread(daemon=True, target=run_scrapers_main).start()
    return {"status": "started"}
