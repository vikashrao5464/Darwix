import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        # Only emit approved fields. Never include exception text, request bodies,
        # prompts, provider responses, credentials, or raw document contents.
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key in ("request_id", "status_code", "error_type", "record_count", "duration_ms", "tool_name",
                    "asr_provider", "confidence", "reason", "audio_duration_ms", "audio_rms_dbfs", "audio_peak_dbfs"):
            if hasattr(record, key):
                event[key] = getattr(record, key)
        return json.dumps(event)


def configure_logging(level: str):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("darwix")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
