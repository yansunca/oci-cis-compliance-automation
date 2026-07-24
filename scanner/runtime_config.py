"""Strict scanner runtime configuration parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


class ConfigError(ValueError):
    """Raised when runtime configuration is invalid."""


@dataclass(frozen=True)
class RuntimeConfig:
    """Validated runtime inputs for a CIS scan wrapper invocation."""

    run_id: str
    tenancy_id: str
    regions: tuple[str, ...]
    level: str
    redact_output: bool
    profile: str

    @classmethod
    def from_mapping(cls, values: Mapping[str, str]) -> RuntimeConfig:
        run_id = _required(values, "OCI_CIS_RUN_ID")
        tenancy_id = _required(values, "OCI_CIS_TENANCY_ID")
        regions = _parse_regions(_required(values, "OCI_CIS_REGIONS"))
        level = values.get("OCI_CIS_LEVEL", "2")
        if level not in {"1", "2"}:
            raise ConfigError(f"invalid CIS level: {level}")
        redact_output = _parse_bool(values.get("OCI_CIS_REDACT_OUTPUT", "true"))
        profile = values.get("OCI_CIS_PROFILE", "DEFAULT").strip()
        if not profile:
            raise ConfigError("OCI_CIS_PROFILE must not be empty")

        return cls(
            run_id=run_id,
            tenancy_id=tenancy_id,
            regions=regions,
            level=level,
            redact_output=redact_output,
            profile=profile,
        )


def _required(values: Mapping[str, str], name: str) -> str:
    value = values.get(name, "").strip()
    if not value:
        raise ConfigError(f"missing required configuration: {name}")
    return value


def _parse_regions(value: str) -> tuple[str, ...]:
    regions = tuple(item.strip() for item in value.split(",") if item.strip())
    if not regions:
        raise ConfigError("OCI_CIS_REGIONS must contain at least one region")
    if len(set(regions)) != len(regions):
        raise ConfigError("OCI_CIS_REGIONS contains duplicate regions")
    return regions


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    raise ConfigError(f"invalid boolean value: {value}")
