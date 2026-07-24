"""Evidence, manifest, and run-ready helpers."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

from scanner.source_contract import normalized_schema_hash


def sha256_file(path: Path) -> str:
    """Calculate a file SHA-256 hex digest."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_file_manifest(path: Path, *, root: Path, category: str) -> dict[str, Any]:
    """Build one manifest file entry."""

    row_count: int | None = None
    schema_hash: str | None = None
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle)
            headers = next(reader, [])
            row_count = sum(1 for _ in reader)
            schema_hash = normalized_schema_hash(headers)
    return {
        "path": path.relative_to(root).as_posix(),
        "category": category,
        "format": _format_for(path),
        "checksum": "sha256:" + sha256_file(path),
        "sizeBytes": path.stat().st_size,
        "rowCount": row_count,
        "schemaHash": schema_hash,
        "controlHint": _control_hint(path),
        "requiredForCompleteness": True,
    }


def build_manifest(
    *,
    run_id: str,
    tenancy_id: str,
    started_at: str,
    completed_at: str | None,
    scanner: dict[str, Any],
    benchmark: dict[str, Any],
    requested_regions: list[str],
    completed_regions: list[str],
    files: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a successful scan manifest envelope."""

    return {
        "contractVersion": "1.0",
        "runId": run_id,
        "tenancyId": tenancy_id,
        "status": "SUCCESS",
        "startedAt": started_at,
        "completedAt": completed_at,
        "trigger": "TEST",
        "executionProfile": "CIS_LEVEL_2_REDACTED",
        "scanner": scanner,
        "benchmark": benchmark,
        "scope": {
            "rootCompartmentId": tenancy_id,
            "requestedRegions": requested_regions,
            "completedRegions": completed_regions,
            "excludedCompartments": [],
        },
        "files": files,
        "completeness": {
            "expectedFileCount": len(files),
            "actualFileCount": len(files),
            "permissionErrorCount": 0,
            "schemaErrorCount": 0,
            "isComplete": True,
            "notes": None,
        },
        "errors": [],
        "metadata": {},
    }


def build_run_ready(
    *,
    run_id: str,
    manifest_path: str,
    manifest_checksum: str,
    published_at: str,
    landing_file_count: int,
    landing_record_count: int,
    requested_regions: list[str],
    completed_regions: list[str],
) -> dict[str, Any]:
    """Build a run-ready record for a complete successful run."""

    return {
        "contractVersion": "1.0",
        "runId": run_id,
        "manifestPath": manifest_path,
        "manifestChecksum": manifest_checksum,
        "publishedAt": published_at,
        "expectedLandingFiles": landing_file_count,
        "actualLandingFiles": landing_file_count,
        "expectedLandingRecords": landing_record_count,
        "actualLandingRecords": landing_record_count,
        "requestedRegions": requested_regions,
        "completedRegions": completed_regions,
        "permissionErrorCount": 0,
        "schemaErrorCount": 0,
        "isReadyForNormalization": True,
        "blockingReasons": [],
    }


def _format_for(path: Path) -> str:
    return {
        ".csv": "CSV",
        ".html": "HTML",
        ".json": "JSON",
        ".jsonl": "JSONL",
        ".txt": "TEXT",
    }.get(path.suffix.lower(), "OTHER")


def _control_hint(path: Path) -> str | None:
    match = __import__("re").search(r"_(\d+(?:-\d+)+)\.csv$", path.name)
    return match.group(1).replace("-", ".") if match else None
