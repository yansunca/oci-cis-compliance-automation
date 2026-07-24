"""Structured operational log envelope helpers."""

from __future__ import annotations

from typing import Any


ALLOWED_EXTRA_KEYS = {
    "finding_id",
    "schema_hash",
    "configuration_version",
    "integration_event_id",
    "duration_ms",
    "error_code",
}


def make_log_event(
    *,
    level: str,
    component: str,
    event_type: str,
    message: str,
    timestamp: str,
    run_id: str | None = None,
    source_file: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a safe structured log event without raw payload fields."""

    event: dict[str, Any] = {
        "timestamp": timestamp,
        "level": level,
        "service": "oci-cis-findings-op",
        "component": component,
        "event_type": event_type,
        "run_id": run_id,
        "source_file": source_file,
        "message": message,
    }
    for key, value in (extra or {}).items():
        if key in ALLOWED_EXTRA_KEYS:
            event[key] = value
    return event
