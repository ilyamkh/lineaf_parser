"""Scrape run API endpoints: run log, freshness, and manual trigger."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from lineaf.database import get_db
from lineaf.models.scrape_run import ScrapeRun
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


@router.get("/runs")
def get_runs(db: Session = Depends(get_db)):
    """Return scrape runs ordered by started_at desc, limit 50."""
    runs = (
        db.query(ScrapeRun)
        .order_by(ScrapeRun.started_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": r.id,
            "site": r.site,
            "status": r.status,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "products_found": r.products_found,
            "products_new": r.products_new,
            "products_removed": r.products_removed,
            "error_message": r.error_message,
        }
        for r in runs
    ]


@router.get("/runs/freshness")
def get_freshness(db: Session = Depends(get_db)):
    """Return latest successful run per site with staleness indicator.

    A site is considered stale if its last successful run was more than
    8 days ago or if there has never been a successful run.
    """
    stale_cutoff = datetime.now(timezone.utc) - timedelta(days=8)

    # Get all distinct sites
    sites = db.query(ScrapeRun.site).distinct().all()

    result = []
    for (site,) in sites:
        latest_success = (
            db.query(ScrapeRun)
            .filter(ScrapeRun.site == site, ScrapeRun.status == "success")
            .order_by(ScrapeRun.finished_at.desc())
            .first()
        )

        if latest_success and latest_success.finished_at:
            finished = latest_success.finished_at
            last_success_str = finished.isoformat()
            # Handle naive datetimes from SQLite (no tz info)
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=timezone.utc)
            is_stale = finished < stale_cutoff
        else:
            last_success_str = None
            is_stale = True

        result.append({
            "site": site,
            "last_success": last_success_str,
            "is_stale": is_stale,
        })

    return result
