"""Standalone scheduler for all ingestors (the docker-compose `ingestion` service entrypoint).

Schedules (UTC):
- PortWatch: daily at 15:10 — data refreshes weekly (Tue 9 AM ET ≈ 13/14:00 UTC);
  daily runs are cheap because fetches are incremental and upserts idempotent.
- GDELT: every 15 minutes (source cadence).
- USGS + GDACS: every 30 minutes.

A failing job logs and retries at the next tick; jobs never overlap (max_instances=1).
The owner may mirror these schedules in n8n later — each module stays runnable via CLI.

CLI:  python -m meridian_ingest.scheduler
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.blocking import BlockingScheduler

from . import comtrade, gdelt, hazards, portwatch
from .settings import Settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main() -> None:
    sched = BlockingScheduler(timezone="UTC", job_defaults={
        "max_instances": 1, "coalesce": True, "misfire_grace_time": 600,
    })
    # next_run_time staggers an immediate first fill so a fresh deployment has data
    # within minutes instead of waiting for the first cron tick.
    now = datetime.now(timezone.utc)
    sched.add_job(lambda: portwatch.ingest("all"), "cron", hour=15, minute=10,
                  id="portwatch", next_run_time=now)
    sched.add_job(gdelt.run, "cron", minute="*/15", id="gdelt",
                  next_run_time=now + timedelta(seconds=30))
    sched.add_job(lambda: hazards.run("all"), "cron", minute="5,35", id="hazards",
                  next_run_time=now + timedelta(seconds=60))
    if Settings().comtrade_api_key:
        sched.add_job(lambda: comtrade.run(datetime.now(timezone.utc).year - 1),
                      "cron", day_of_week="sun", hour=3, id="comtrade",
                      next_run_time=now + timedelta(seconds=90))
    logging.getLogger(__name__).info("scheduler started: %s", [j.id for j in sched.get_jobs()])
    sched.start()


if __name__ == "__main__":
    main()
