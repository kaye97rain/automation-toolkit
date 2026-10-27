"""Logging to console and to a rotating file in logs/."""

import logging
from logging.handlers import RotatingFileHandler

from core import config


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(config.get("LOG_LEVEL", "INFO"))
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    file = RotatingFileHandler(
        config.LOG_DIR / f"{name}.log", maxBytes=1_000_000, backupCount=5, encoding="utf-8"
    )
    file.setFormatter(fmt)
    logger.addHandler(file)
    return logger
