import json
import logging
import traceback
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exc_info"] = traceback.format_exception(*record.exc_info)
        return json.dumps(log_entry)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logging.root.setLevel(level.upper())
    logging.root.handlers = [handler]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
