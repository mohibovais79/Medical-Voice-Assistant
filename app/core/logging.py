"""Structured logging setup.

Logs are written to stdout (Render captures stdout). Format is JSON-ish so it
can be parsed by log aggregators, but stays human-readable for local dev.
"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger once."""
    root = logging.getLogger()
    if root.handlers:
        return  # already configured

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
