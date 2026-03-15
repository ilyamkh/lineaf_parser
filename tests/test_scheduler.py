"""Tests for APScheduler weekly scrape job."""

from __future__ import annotations

import pytest
from apscheduler.triggers.cron import CronTrigger

from lineaf.scheduler import scheduler, start_scheduler, stop_scheduler


@pytest.fixture(autouse=True)
def _cleanup_scheduler():
    """Ensure scheduler is stopped after each test."""
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


def test_cron_trigger():
    """Scheduler registers weekly_scrape job with Monday 03:00 Moscow time."""
    start_scheduler()
    job = scheduler.get_job("weekly_scrape")
    assert job is not None, "weekly_scrape job must be registered"

    trigger = job.trigger
    assert isinstance(trigger, CronTrigger)
    # CronTrigger stores fields; check day_of_week, hour, minute
    fields = {f.name: str(f) for f in trigger.fields}
    assert fields["day_of_week"] == "mon"
    assert fields["hour"] == "3"
    assert fields["minute"] == "0"
    assert str(trigger.timezone) == "Europe/Moscow"


def test_scheduler_start_stop():
    """Start and stop scheduler without error."""
    start_scheduler()
    assert scheduler.running is True
    stop_scheduler()
    assert scheduler.running is False
