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

from apscheduler.schedulers.blocking import BlockingScheduler

from . import gdelt, hazards, portwatch

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


def main() -> None:
    sched = BlockingScheduler(timezone="UTC", job_defaults={
        "max_instances": 1, "coalesce": True, "misfire_grace_time": 600,
    })
    sched.add_job(lambda: portwatch.ingest("all"), "cron", hour=15, minute=10, id="portwatch")
    sched.add_job(gdelt.run, "cron", minute="*/15", id="gdelt")
    sched.add_job(lambda: hazards.run("all"), "cron", minute="5,35", id="hazards")
    logging.getLogger(__name__).info("scheduler started: %s", [j.id for j in sched.get_jobs()])
    sched.start()


if __name__ == "__main__":
    main()
