"""Source contract helpers for OCI CIS checker output.

The scanner wrapper and database loader share these rules so source-specific
format behavior remains metadata-driven instead of parser-branch driven.
"""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROHIBITED_MARKERS = re.compile(
    r"ocid1\.|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|PRIVATE KEY|"
    r"Authorization:|Bearer ",
)


class ContractError(ValueError):
    """Raised when source output violates the approved contract."""


@dataclass(frozen=True)
class SourceProfile:
    """Approved header contract for a family of OCI CIS output files."""

    profile_id: str
    display_name: str
    schema_hash: str
    required_headers: tuple[str, ...]
    aliases: dict[str, str]


@dataclass(frozen=True)
class CsvSchemaResult:
    """Classification for a CSV file against an approved source profile."""

    profile_id: str
    status: str
    schema_hash: str
    observed_headers: tuple[str, ...]
    canonical_headers: tuple[str, ...]
    missing_required_headers: list[str]
    additional_headers: list[str]
    aliases_applied: dict[str, str]


@dataclass(frozen=True)
class RunReadinessResult:
    """Readiness classification for manifest plus run-ready metadata."""

    is_ready: bool
    blocking_reasons: list[str]


SOURCE_PROFILES: dict[str, SourceProfile] = {
    "asset-management-resource": SourceProfile(
        profile_id="asset-management-resource",
        display_name="Asset Management root-compartment CSV",
        schema_hash="sha256:ed0d697e6bd0e521962d6aa1722c64f0e8ef883de36ba59110473ee34d037a54",
        required_headers=("display_name", "id", "region", "extract_date"),
        aliases={},
    ),
    "compute-instance": SourceProfile(
        profile_id="compute-instance",
        display_name="Compute finding CSV",
        schema_hash="sha256:f8f2ad431e88e03b7bfb34cdb4224ebbb5207518e986e1981f4408d3e943b2c0",
        required_headers=(
            "availability_domain",
            "capacity_reservation_id",
            "compartment_id",
            "cluster_placement_group_id",
            "dedicated_vm_host_id",
            "defined_tags",
            "security_attributes",
            "security_attributes_state",
            "display_name",
            "extended_metadata",
            "fault_domain",
            "freeform_tags",
            "id",
            "image_id",
            "ipxe_script",
            "launch_mode",
            "launch_options",
            "instance_options",
            "availability_config",
            "preemptible_instance_config",
            "lifecycle_state",
            "metadata",
            "region",
            "shape",
            "shape_config",
            "is_cross_numa_node",
            "source_details",
            "system_tags",
            "time_created",
            "agent_config",
            "time_maintenance_reboot_due",
            "platform_config",
            "instance_configuration_id",
            "licensing_configs",
            "deep_link",
            "error",
            "extract_date",
        ),
        aliases={},
    ),
    "iam-identity-domain": SourceProfile(
        profile_id="iam-identity-domain",
        display_name="IAM identity-domain password policy CSV",
        schema_hash="sha256:e8496a2d866951be2b0e4a04151e3c2a43c4b7295e172c467740ebaa6d6244f2",
        required_headers=(
            "id",
            "compartment_id",
            "display_name",
            "home_region",
            "type",
            "lifecycle_state",
            "identitydomainclient",
            "password_policy",
            "extract_date",
        ),
        aliases={},
    ),
    "iam-user-mfa": SourceProfile(
        profile_id="iam-user-mfa",
        display_name="IAM user MFA CSV",
        schema_hash="sha256:0d7e602dee99ab271d2ee27868d2a391457892b8b90b79d656f04d72cef649ef",
        required_headers=(
            "id",
            "domain_deeplink",
            "name",
            "deep_link",
            "defined_tags",
            "description",
            "email",
            "email_verified",
            "external_identifier",
            "is_federated",
            "is_mfa_activated",
            "lifecycle_state",
            "time_created",
            "can_use_api_keys",
            "can_use_auth_tokens",
            "can_use_console_password",
            "can_use_customer_secret_keys",
            "can_use_db_credentials",
            "can_use_o_auth2_client_credentials",
            "can_use_smtp_credentials",
            "groups",
            "api_keys",
            "auth_tokens",
            "customer_secret_keys",
            "database_passwords",
            "extract_date",
        ),
        aliases={"user_id": "id", "user_name": "name"},
    ),
    "network-security-list": SourceProfile(
        profile_id="network-security-list",
        display_name="Networking security-list CSV",
        schema_hash="sha256:7862214963cc073f57625aed2aec0e8da9e80e8c683800e5d2465d0e8454f650",
        required_headers=(
            "id",
            "display_name",
            "compartment_id",
            "deep_link",
            "lifecycle_state",
            "time_created",
            "vcn_id",
            "region",
            "freeform_tags",
            "defined_tags",
            "ingress_security_rules",
            "egress_security_rules",
            "extract_date",
        ),
        aliases={"security_list_id": "id", "security_list_name": "display_name"},
    ),
    "object-storage-bucket": SourceProfile(
        profile_id="object-storage-bucket",
        display_name="Object Storage bucket CSV",
        schema_hash="sha256:51ce8248abc10045a11ae4511e9fb96e13927726d1d6fb461e0a0c4cffb7d1a8",
        required_headers=(
            "id",
            "name",
            "deep_link",
            "kms_key_id",
            "namespace",
            "compartment_id",
            "object_events_enabled",
            "public_access_type",
            "replication_enabled",
            "is_read_only",
            "storage_tier",
            "time_created",
            "versioning",
            "defined_tags",
            "freeform_tags",
            "region",
            "notes",
            "extract_date",
        ),
        aliases={"bucket_id": "id", "bucket_name": "name"},
    ),
    "analytics-instance": SourceProfile(
        profile_id="analytics-instance",
        display_name="Oracle Analytics Cloud instance CSV",
        schema_hash="sha256:a69f45cf157e7bea486b8507d6ce4930e1dc5daf56028badccfb1cc2be2487bb",
        required_headers=(
            "id",
            "name",
            "deep_link",
            "network_endpoint_details",
            "network_endpoint_type",
            "compartment_id",
            "lifecycle_state",
            "service_url",
            "region",
            "extract_date",
        ),
        aliases={},
    ),
    "autonomous-database": SourceProfile(
        profile_id="autonomous-database",
        display_name="Autonomous Database CSV",
        schema_hash="sha256:e42b1708ae5ca8c68a29746ee9062dfdcc39a4ba632752188b99158a954b5fa4",
        required_headers=(
            "id",
            "compartment_id",
            "lifecycle_state",
            "db_name",
            "display_name",
            "service_console_url",
            "db_version",
            "db_workload",
            "is_mtls_connection_required",
            "deep_link",
            "extract_date",
        ),
        aliases={},
    ),
    "block-volume": SourceProfile(
        profile_id="block-volume",
        display_name="Block Volume CSV",
        schema_hash="sha256:7cf0525824e557576d2e034bf5880588b52969b28299ea2500d7b9555baab88f",
        required_headers=(
            "id",
            "display_name",
            "deep_link",
            "kms_key_id",
            "lifecycle_state",
            "compartment_id",
            "size_in_gbs",
            "availability_domain",
            "region",
            "extract_date",
        ),
        aliases={},
    ),
    "boot-volume": SourceProfile(
        profile_id="boot-volume",
        display_name="Boot Volume CSV",
        schema_hash="sha256:66e16c0fda2b143ff846c2c6289dd00e324ed891974132c795a55355bb78f81f",
        required_headers=(
            "id",
            "display_name",
            "deep_link",
            "kms_key_id",
            "lifecycle_state",
            "compartment_id",
            "size_in_gbs",
            "availability_domain",
            "region",
            "extract_date",
        ),
        aliases={},
    ),
}


def normalize_header(value: str) -> str:
    """Normalize a source header for stable hashing and alias lookup."""

    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def normalized_schema_hash(headers: list[str] | tuple[str, ...]) -> str:
    """Return the approved schema hash algorithm for an ordered header list."""

    normalized = "\n".join(normalize_header(item) for item in headers)
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def classify_csv_schema(path: Path, profile_id: str) -> CsvSchemaResult:
    """Classify a CSV file as exact, aliased, additive, or invalid."""

    profile = SOURCE_PROFILES.get(profile_id)
    if profile is None:
        raise ContractError(f"unknown source profile: {profile_id}")

    rows = _read_csv_rows(path)
    if not rows or not rows[0]:
        raise ContractError(f"malformed CSV: {path} has no header row")

    observed_headers = tuple(normalize_header(item) for item in rows[0])
    canonical_headers = tuple(profile.aliases.get(item, item) for item in observed_headers)
    aliases_applied = {
        observed: canonical
        for observed, canonical in zip(observed_headers, canonical_headers, strict=True)
        if observed != canonical
    }
    missing = [header for header in profile.required_headers if header not in canonical_headers]
    if missing:
        raise ContractError(f"missing required headers for {profile_id}: {', '.join(missing)}")

    required_set = set(profile.required_headers)
    additional = [header for header in canonical_headers if header not in required_set]
    schema_hash = normalized_schema_hash(list(canonical_headers))
    if aliases_applied:
        status = "ALIASED"
    elif schema_hash == profile.schema_hash:
        status = "EXACT"
    elif additional:
        status = "ADDITIVE"
    else:
        status = "COMPATIBLE"

    return CsvSchemaResult(
        profile_id=profile.profile_id,
        status=status,
        schema_hash=schema_hash,
        observed_headers=observed_headers,
        canonical_headers=canonical_headers,
        missing_required_headers=missing,
        additional_headers=additional,
        aliases_applied=aliases_applied,
    )


def detect_source_profile(path: Path) -> CsvSchemaResult:
    """Detect the approved source profile for a CSV from its headers."""

    rows = _read_csv_rows(path)
    if not rows or not rows[0]:
        raise ContractError(f"malformed CSV: {path} has no header row")
    observed_hash = normalized_schema_hash(rows[0])
    for profile in SOURCE_PROFILES.values():
        if observed_hash == profile.schema_hash:
            return classify_csv_schema(path, profile.profile_id)

    compatible: list[CsvSchemaResult] = []
    for profile in SOURCE_PROFILES.values():
        try:
            compatible.append(classify_csv_schema(path, profile.profile_id))
        except ContractError:
            continue
    if compatible:
        compatible.sort(
            key=lambda result: len(SOURCE_PROFILES[result.profile_id].required_headers),
            reverse=True,
        )
        if len(compatible) == 1:
            return compatible[0]
        top = compatible[0]
        runner_up = compatible[1]
        if len(SOURCE_PROFILES[top.profile_id].required_headers) > len(
            SOURCE_PROFILES[runner_up.profile_id].required_headers,
        ):
            return top
        profiles = ", ".join(result.profile_id for result in compatible)
        raise ContractError(f"ambiguous source schema for {path}: {profiles}")
    raise ContractError(f"unknown source schema for {path}")


def validate_unique_source_files(paths: list[Path]) -> None:
    """Reject duplicate source file basenames in one run package."""

    seen: set[str] = set()
    for path in paths:
        key = path.name
        if key in seen:
            raise ContractError(f"duplicate source file: {key}")
        seen.add(key)


def classify_run_ready(manifest: dict[str, Any], run_ready: dict[str, Any]) -> RunReadinessResult:
    """Evaluate whether a manifest/run-ready pair can enter normalization."""

    reasons: list[str] = []
    completeness = manifest.get("completeness", {})
    if manifest.get("status") != "SUCCESS":
        reasons.append("manifest status is not SUCCESS")
    if not completeness.get("isComplete"):
        reasons.append("manifest is not complete")
    if completeness.get("expectedFileCount") != completeness.get("actualFileCount"):
        reasons.append("manifest file counts do not match")
    if completeness.get("permissionErrorCount", 0) > 0:
        reasons.append("manifest has permission errors")
    if completeness.get("schemaErrorCount", 0) > 0:
        reasons.append("manifest has schema errors")
    if sorted(manifest.get("scope", {}).get("requestedRegions", [])) != sorted(
        manifest.get("scope", {}).get("completedRegions", []),
    ):
        reasons.append("manifest region coverage is incomplete")
    if not run_ready.get("isReadyForNormalization"):
        reasons.append("run_ready is not ready for normalization")
    if run_ready.get("expectedLandingFiles") != run_ready.get("actualLandingFiles"):
        reasons.append("landing file counts do not match")
    if run_ready.get("expectedLandingRecords") != run_ready.get("actualLandingRecords"):
        reasons.append("landing record counts do not match")
    if run_ready.get("permissionErrorCount", 0) > 0:
        reasons.append("run_ready has permission errors")
    if run_ready.get("schemaErrorCount", 0) > 0:
        reasons.append("run_ready has schema errors")
    if run_ready.get("blockingReasons"):
        reasons.append("run_ready includes blocking reasons")

    return RunReadinessResult(is_ready=not reasons, blocking_reasons=reasons)


def check_no_prohibited_markers(root: Path) -> None:
    """Scan committed fixture files for markers that must not enter Git."""

    paths = [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        match = PROHIBITED_MARKERS.search(text)
        if match:
            raise ContractError(f"prohibited marker in {path}: {match.group(0)}")


def _read_csv_rows(path: Path) -> list[list[str]]:
    data = path.read_bytes()
    if b"\x00" in data:
        raise ContractError(f"malformed CSV: {path} contains NUL bytes")
    text = data.decode("utf-8")
    try:
        rows = list(csv.reader(text.splitlines()))
    except csv.Error as exc:
        raise ContractError(f"malformed CSV: {path}: {exc}") from exc

    if rows:
        expected = len(rows[0])
        for line_number, row in enumerate(rows[1:], start=2):
            if len(row) != expected:
                raise ContractError(
                    f"malformed CSV: {path} line {line_number} has {len(row)} columns; "
                    f"expected {expected}",
                )
    return rows
