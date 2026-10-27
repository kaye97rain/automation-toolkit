"""Wrap a job so every run is logged, timed, and failures can raise an alert."""

import time
import traceback
from collections.abc import Callable

from core import config, notify
from core.logger import get_logger


def run_job(name: str, job: Callable[[], object], alert_on_failure: bool = False) -> object:
    log = get_logger(name)
    log.info("Job started")
    start = time.perf_counter()
    try:
        result = job()
        log.info("Job finished in %.1fs", time.perf_counter() - start)
        return result
    except Exception:
        log.error("Job failed:\n%s", traceback.format_exc())
        if alert_on_failure and config.get("SLACK_WEBHOOK_URL"):
            notify.send_slack(f":rotating_light: Automation *{name}* failed. Check logs/{name}.log")
        raise
