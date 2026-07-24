"""Dry-run validation for local wrapper output before database loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scanner.evidence import sha256_file


@dataclass(frozen=True)
class StagingValidationResult:
    """Dry-run validation result for wrapper staging output."""

    is_valid: bool
    errors: list[str]
    counts: dict[str, int]


def validate_staging_run(run_dir: Path) -> StagingValidationResult:
    """Validate local wrapper output without connecting to ADB."""

    errors: list[str] = []
    counts: dict[str, int] = {}
    if not (run_dir / "_SUCCESS").is_file():
        errors.append("missing _SUCCESS marker")
    if (run_dir / "_FAILED").exists():
        errors.append("_FAILED marker is present")
    for required in ("manifest.json", "run_ready.json"):
        if not (run_dir / required).is_file():
            errors.append(f"missing {required}")

    manifest = _read_json(run_dir / "manifest.json", errors)
    if manifest:
        _validate_manifest_files(run_dir, manifest, errors)

    counts["scan_run"] = _count_jsonl(run_dir / "staging" / "scan_run.jsonl", errors)
    scan_file_rows = _read_jsonl(run_dir / "staging" / "scan_file.jsonl", errors)
    counts["scan_file"] = len(scan_file_rows)
    counts["config_version"] = _count_jsonl(run_dir / "config" / "config_version.jsonl", errors)
    counts["source_profile"] = _count_jsonl(run_dir / "config" / "source_profile.jsonl", errors)
    counts["field_alias"] = _count_jsonl(run_dir / "config" / "field_alias.jsonl", errors)
    raw_rows = _read_jsonl(run_dir / "raw" / "records-00001.jsonl", errors)
    counts["raw_cis_record"] = len(raw_rows)
    canonical_rows = _read_jsonl(run_dir / "canonical" / "findings-00001.jsonl", errors)
    counts["canonical_finding"] = len(canonical_rows)
    canonical_stage_rows = _read_jsonl(
        run_dir / "staging" / "canonical_finding_stage.jsonl",
        errors,
    )
    counts["canonical_finding_stage"] = len(canonical_stage_rows)

    scan_file_paths = {row.get("source_path") for row in scan_file_rows}
    for index, row in enumerate(raw_rows, start=1):
        if row.get("scan_file_path") not in scan_file_paths:
            errors.append(f"raw row {index} references unknown scan_file_path")
        if not _is_json_string(row.get("payload_json")):
            errors.append(f"raw row {index} payload_json is not valid JSON")
    for index, row in enumerate(canonical_rows, start=1):
        if not isinstance(row.get("findingId"), str) or not row["findingId"]:
            errors.append(f"canonical row {index} missing findingId")
        source_lineage = row.get("sourceLineage")
        if not isinstance(source_lineage, dict) or source_lineage.get("runId") is None:
            errors.append(f"canonical row {index} missing sourceLineage.runId")
    for index, row in enumerate(canonical_stage_rows, start=1):
        canonical_json = row.get("canonical_json")
        if not _is_json_string(canonical_json):
            errors.append(f"canonical stage row {index} canonical_json is not valid JSON")
            continue
        finding = json.loads(canonical_json)
        if row.get("run_id") != finding.get("sourceLineage", {}).get("runId"):
            errors.append(f"canonical stage row {index} run_id does not match canonical_json")
        if row.get("finding_id") != finding.get("findingId"):
            errors.append(f"canonical stage row {index} finding_id does not match canonical_json")

    return StagingValidationResult(is_valid=not errors, errors=errors, counts=counts)


def _validate_manifest_files(run_dir: Path, manifest: dict[str, Any], errors: list[str]) -> None:
    for file_entry in manifest.get("files", []):
        path = run_dir / file_entry.get("path", "")
        if not path.is_file():
            errors.append(f"manifest file missing: {file_entry.get('path')}")
            continue
        expected = file_entry.get("checksum")
        actual = "sha256:" + sha256_file(path)
        if expected != actual:
            errors.append(f"checksum mismatch: {file_entry.get('path')}")


def _read_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON: {path.name}: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"invalid JSON object: {path.name}")
        return None
    return data


def _read_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    if not path.is_file():
        errors.append(f"missing {path.relative_to(path.parents[1]).as_posix()}")
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSONL {path.name}:{line_number}: {exc}")
            continue
        if not isinstance(row, dict):
            errors.append(f"invalid JSONL object {path.name}:{line_number}")
            continue
        rows.append(row)
    return rows


def _count_jsonl(path: Path, errors: list[str]) -> int:
    return len(_read_jsonl(path, errors))


def _is_json_string(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        json.loads(value)
    except json.JSONDecodeError:
        return False
    return True
