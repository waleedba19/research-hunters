"""
logger.py — Timestamped logging to file + console.
Used by every module in the v4 stack.
"""
import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

DEFAULT_LOG_DIR = os.path.join(os.path.dirname(__file__), "data", "logs")


def get_logger(name: str, log_dir: str = DEFAULT_LOG_DIR) -> logging.Logger:
    """Return a logger that writes to console + rotating file in data/logs/."""
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # File (10 MB x 5)
    log_file = os.path.join(
        log_dir, f"{name}_{datetime.utcnow().strftime('%Y%m%d')}.log"
    )
    fh = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
