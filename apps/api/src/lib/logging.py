"""Structured logging with PII redaction.

JSON logs without PII. RUTs, passwords, certificate material, JWT claims and
SII payloads are masked by `filter_sensitive` before reaching any sink.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import MutableMapping
from typing import Any, cast

import structlog

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "rut",
        "password",
        "pfx",
        "pfx_bytes",
        "pfx_password",
        "claim",
        "claims",
        "token",
        "access_token",
        "refresh_token",
        "razon_social",
        "monto",
        "raw_payload",
        "kms_data_key",
    }
)


def filter_sensitive(
    _logger: Any,
    _method: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    for k in list(event_dict):
        if k.lower() in SENSITIVE_KEYS:
            event_dict[k] = "***"
    return event_dict


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            filter_sensitive,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))
