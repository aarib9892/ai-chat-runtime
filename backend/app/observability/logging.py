import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from app.config.settings import settings

request_id_context: ContextVar[str | None] = ContextVar(
    "request_id",
    default=None,
)


class JsonFormatter(logging.Formatter):

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:

        payload: dict[str, Any] = {
            "timestamp": (datetime.now(timezone.utc).isoformat()),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = request_id_context.get()

        if request_id:
            payload["request_id"] = request_id

        # Extra structured fields we allow.
        structured_fields = [
            "conversation_id",
            "user_message_id",
            "assistant_message_id",
            "step",
            "tool_name",
            "call_id",
            "response_id",
            "status",
            "outcome",
            "reason",
            "duration_ms",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "estimated_cost_usd",
        ]

        for field in structured_fields:
            value = getattr(
                record,
                field,
                None,
            )

            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(
            payload,
            default=str,
        )


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(JsonFormatter())

    app_logger = logging.getLogger("app")

    app_logger.setLevel(settings.log_level)

    app_logger.handlers.clear()

    app_logger.addHandler(handler)

    app_logger.propagate = False
