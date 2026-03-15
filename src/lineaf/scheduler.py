"""APScheduler configuration for weekly automatic scraping."""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from lineaf.run_scrapers import main as run_scrapers_main

scheduler = BackgroundScheduler()


def start_scheduler() -> None:
    """Register the weekly scrape job and start the scheduler.

    Job runs every Monday at 03:00 Moscow time.
    Must only be called from FastAPI lifespan (not at import time)
    to prevent duplicate starts on uvicorn reload.
    """
    scheduler.add_job(
        run_scrapers_main,
        trigger=CronTrigger(
            day_of_week="mon",
            hour=3,
            minute=0,
            timezone="Europe/Moscow",
        ),
        id="weekly_scrape",
        replace_existing=True,
    )
    scheduler.start()


def stop_scheduler() -> None:
    """Shut down the scheduler without waiting for running jobs."""
    scheduler.shutdown(wait=False)
