"""Canonical finding normalization for approved wrapper landing records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from scanner.source_contract import SOURCE_PROFILES

NORMALIZER_VERSION = "0.1.0"
CONFIGURATION_VERSION = "source-contract-v1"


@dataclass(frozen=True)
class ControlDefaults:
    """Minimal control defaults used before the database rule table exists."""

    section: str
    title: str
    cis_level: str | None
    priority: str
    risk_score: int


CONTROL_DEFAULTS: dict[str, ControlDefaults] = {
    "2.1": ControlDefaults(
        section="Networking",
        title="Synthetic networking control",
        cis_level="1",
        priority="HIGH",
        risk_score=75,
    ),
    "3.2": ControlDefaults(
        section="Compute",
        title="Synthetic compute control",
        cis_level="2",
        priority="MEDIUM",
        risk_score=50,
    ),
}


def normalize_landing_record(
    landing_record: dict[str, Any],
    *,
    tenancy_id: str,
) -> dict[str, Any]:
    """Normalize one landing record into the canonical finding contract."""

    payload = _payload(landing_record)
    profile_id = _profile_id_for_landing_record(landing_record)
    control_hint = landing_record.get("controlHint") or profile_id
    defaults = CONTROL_DEFAULTS.get(
        str(control_hint),
        ControlDefaults(
            section="Unknown",
            title=f"OCI CIS control {control_hint}",
            cis_level=None,
            priority="INFORMATIONAL",
            risk_score=0,
        ),
    )
    resource_key = _first_present(payload, ("id", "name", "display_name"))
    region = _blank_to_none(payload.get("region"))
    compartment_id = _first_present(payload, ("compartment_id", "id")) or "UNKNOWN"
    scope_type = "RESOURCE" if resource_key else "COMPARTMENT"
    scope_key = resource_key or compartment_id
    benchmark_version = str(landing_record["benchmarkVersion"])
    control = {
        "lineageId": _control_lineage_id(benchmark_version, str(control_hint)),
        "displayId": str(control_hint),
        "title": defaults.title,
        "section": defaults.section,
        "cisLevel": defaults.cis_level,
        "benchmarkVersion": benchmark_version,
    }
    scope = {"type": scope_type, "key": scope_key, "region": region}
    return {
        "contractVersion": "1.0",
        "findingId": stable_finding_id(
            tenancy_id=tenancy_id,
            benchmark_version=benchmark_version,
            control_display_id=str(control_hint),
            scope_type=scope_type,
            scope_key=scope_key,
            region=region,
        ),
        "tenancyId": tenancy_id,
        "control": control,
        "scope": scope,
        "resource": _resource(profile_id, payload, resource_key, region) if resource_key else None,
        "compartment": {
            "ocid": compartment_id,
            "name": compartment_id,
            "path": f"/{compartment_id}",
            "parentOcid": None,
        },
        "product": None,
        "state": "NEW",
        "priority": defaults.priority,
        "riskScore": defaults.risk_score,
        "owner": None,
        "firstSeenAt": landing_record["recordedAt"],
        "lastSeenAt": landing_record["recordedAt"],
        "lastStateChangeAt": landing_record["recordedAt"],
        "resolvedAt": None,
        "dueAt": None,
        "evidenceSummary": f"{SOURCE_PROFILES[profile_id].display_name} observed by OCI CIS checker.",
        "remediation": None,
        "externalReference": None,
        "sourceLineage": {
            "runId": landing_record["runId"],
            "sourceObjectUri": landing_record.get("sourceObjectUri"),
            "sourceFile": landing_record["sourceFile"],
            "sourceRow": landing_record["sourceRow"],
            "schemaHash": landing_record["schemaHash"],
            "scannerVersion": landing_record["scannerVersion"],
            "benchmarkVersion": benchmark_version,
            "wrapperVersion": None,
            "normalizerVersion": NORMALIZER_VERSION,
            "configurationVersion": CONFIGURATION_VERSION,
        },
        "attributes": {"sourceProfileId": profile_id},
    }


def stable_finding_id(
    *,
    tenancy_id: str,
    benchmark_version: str,
    control_display_id: str,
    scope_type: str,
    scope_key: str,
    region: str | None,
) -> str:
    """Return the stable finding identity for repeated observations of the same finding."""

    material = {
        "benchmarkVersion": benchmark_version,
        "controlDisplayId": control_display_id,
        "region": region,
        "scopeKey": scope_key,
        "scopeType": scope_type,
        "tenancyId": tenancy_id,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return "FND-" + digest[:24].upper()


def _payload(landing_record: dict[str, Any]) -> dict[str, Any]:
    payload = landing_record.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("landing record payload must be an object")
    return payload


def _profile_id_for_schema(schema_hash: str) -> str:
    for profile in SOURCE_PROFILES.values():
        if profile.schema_hash == schema_hash:
            return profile.profile_id
    raise ValueError(f"unsupported schema hash for normalization: {schema_hash}")


def _profile_id_for_landing_record(landing_record: dict[str, Any]) -> str:
    source_profile_id = landing_record.get("sourceProfileId")
    if isinstance(source_profile_id, str) and source_profile_id in SOURCE_PROFILES:
        return source_profile_id
    return _profile_id_for_schema(landing_record["schemaHash"])


def _first_present(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _blank_to_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _control_lineage_id(benchmark_version: str, control_display_id: str) -> str:
    return f"cis-oci-{benchmark_version}-{control_display_id}"


def _resource(
    profile_id: str,
    payload: dict[str, Any],
    resource_key: str,
    region: str | None,
) -> dict[str, Any]:
    return {
        "key": resource_key,
        "ocid": resource_key if resource_key.startswith("ocid1.") else None,
        "name": _blank_to_none(payload.get("display_name") or payload.get("name")),
        "type": profile_id,
        "region": region,
        "lifecycleState": _blank_to_none(payload.get("lifecycle_state")),
    }
