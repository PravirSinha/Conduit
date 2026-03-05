"""
CONDUIT — Base Logger
======================
Single logger instance used across the entire project.
JSON structured output for programmatic querying.
Writes to both console and rotating log file.

All other logging modules import from here:
    from app_logging.logger import get_logger
    logger = get_logger("conduit.agent")
"""

import os
import json
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# ── CONFIG ────────────────────────────────────────────────────────────────────

LOG_LEVEL   = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
LOG_DIR     = Path("logs")


# ── JSON FORMATTER ────────────────────────────────────────────────────────────

class JSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON.
    Makes logs queryable with jq, CloudWatch, Datadog etc.

    Output format:
    2026-02-28 03:57:54,040 | INFO | conduit.agent | {"event": "agent_start", ...}
    """

    def format(self, record: logging.LogRecord) -> str:
        # Base fields always present
        log_entry = {
            "level":   record.levelname,
            "logger":  record.name,
            "ts":      datetime.now(timezone.utc).isoformat(),
        }

        # If message is already a dict — merge directly
        if isinstance(record.msg, dict):
            log_entry.update(record.msg)
        else:
            log_entry["message"] = record.getMessage()

        # Include exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Prefix with timestamp and level for human readability
        timestamp = datetime.fromtimestamp(record.created).strftime(
            "%Y-%m-%d %H:%M:%S,%f"
        )[:-3]

        return (
            f"{timestamp} | "
            f"{record.levelname:<8} | "
            f"{record.name} | "
            f"{json.dumps(log_entry, ensure_ascii=False, default=str)}"
        )


# ── LOGGER FACTORY ────────────────────────────────────────────────────────────

_loggers: dict = {}


def get_logger(name: str = "conduit") -> logging.Logger:
    """
    Returns a configured logger instance.
    Loggers are cached — calling get_logger("conduit.agent") twice
    returns the same instance.

    Args:
        name: Logger name. Use dotted hierarchy:
              "conduit"          → root app logger
              "conduit.agent"    → agent events
              "conduit.api"      → API request/response
              "conduit.pipeline" → orchestrator events
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Prevent duplicate handlers if called multiple times
    if logger.handlers:
        _loggers[name] = logger
        return logger

    formatter = JSONFormatter()

    # ── CONSOLE HANDLER ───────────────────────────────────────────────────
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.addHandler(console_handler)

    # ── FILE HANDLER ──────────────────────────────────────────────────────
    if LOG_TO_FILE:
        LOG_DIR.mkdir(exist_ok=True)

        # Rotating file — max 10MB per file, keep 5 backups
        file_handler = logging.handlers.RotatingFileHandler(
            filename    = LOG_DIR / "conduit.log",
            maxBytes    = 10 * 1024 * 1024,  # 10MB
            backupCount = 5,
            encoding    = "utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)  # file gets everything
        logger.addHandler(file_handler)

        # Separate error log — only WARNING and above
        error_handler = logging.handlers.RotatingFileHandler(
            filename    = LOG_DIR / "conduit_errors.log",
            maxBytes    = 5 * 1024 * 1024,
            backupCount = 3,
            encoding    = "utf-8",
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.WARNING)
        logger.addHandler(error_handler)

    # Don't propagate to root logger — avoid duplicate output
    logger.propagate = False

    _loggers[name] = logger
    return logger


# ── CONVENIENCE INSTANCES ─────────────────────────────────────────────────────
# Import these directly instead of calling get_logger() every time

agent_logger    = get_logger("conduit.agent")
api_logger      = get_logger("conduit.api")
pipeline_logger = get_logger("conduit.pipeline")