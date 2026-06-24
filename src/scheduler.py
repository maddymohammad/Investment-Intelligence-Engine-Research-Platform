"""
APScheduler automation for the daily pipeline.

Runs the full pipeline every weekday (Mon–Fri) at 18:00 IST (12:30 UTC).
Designed to run as a long-lived process (e.g. inside Docker or a systemd service).

Usage:
    python -m src.scheduler          # start the scheduler process
    python src/scheduler.py          # same
"""
from __future__ import annotations

import logging
import signal
import sys
from datetime import datetime

import pytz
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")

# Run at 18:00 IST Mon–Fri (market closes 15:30; we give 2.5h for data to settle)
_HOUR_IST = 18
_MINUTE_IST = 0


def run_pipeline() -> None:
    """Job entry point — executed by APScheduler."""
    from src.pipeline.daily import run_daily
    from src.safeguards import assert_research_only

    assert_research_only()
    logger.info("Scheduler triggered daily pipeline at %s IST", datetime.now(IST).strftime("%H:%M"))
    try:
        recs = run_daily()
        logger.info("Scheduler: pipeline complete — %d recommendation(s)", len(recs))
    except Exception as exc:
        logger.error("Scheduler: pipeline failed — %s", exc, exc_info=True)


def create_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone=IST)
    trigger = CronTrigger(
        day_of_week="mon-fri",
        hour=_HOUR_IST,
        minute=_MINUTE_IST,
        timezone=IST,
    )
    scheduler.add_job(
        run_pipeline,
        trigger=trigger,
        id="daily_pipeline",
        name="Daily investment pipeline",
        max_instances=1,
        coalesce=True,  # skip missed runs if process was down
        misfire_grace_time=3600,  # fire up to 1h late if process starts delayed
    )
    return scheduler


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    scheduler = create_scheduler()

    # Graceful shutdown on SIGTERM / SIGINT
    def _shutdown(signum, frame):
        logger.info("Scheduler received signal %s — shutting down", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    next_run = scheduler.get_jobs()[0].next_run_time
    logger.info(
        "Scheduler started. Next run: %s IST (Mon–Fri %02d:%02d IST)",
        next_run.astimezone(IST).strftime("%Y-%m-%d %H:%M"),
        _HOUR_IST,
        _MINUTE_IST,
    )

    scheduler.start()


if __name__ == "__main__":
    main()
