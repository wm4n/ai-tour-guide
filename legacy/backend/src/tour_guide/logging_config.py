"""Logging setup: human-readable text or JSON, plus log_event() helper."""

import json
import logging
import sys
from datetime import datetime, timezone


class _HumanFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname.ljust(7)
        event = getattr(record, "event", record.getMessage())
        params = getattr(record, "params", {})
        line = f"{ts} {level} [{event}]"
        if params:
            params_str = " ".join(f"{k}={v}" for k, v in params.items())
            line = f"{line}  {params_str}"
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        doc: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": getattr(record, "event", record.getMessage()),
        }
        doc.update(getattr(record, "params", {}))
        if record.exc_info:
            doc["traceback"] = self.formatException(record.exc_info)
        return json.dumps(doc, default=str)


def setup_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Configure root logger. Call once at app startup."""
    formatter: logging.Formatter = _JsonFormatter() if fmt == "json" else _HumanFormatter()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: str = "info",
    exc_info: bool = False,
    **params: object,
) -> None:
    """Emit a structured event log entry."""
    log_fn = getattr(logger, level.lower(), logger.info)
    log_fn("", extra={"event": event, "params": params}, exc_info=exc_info)
