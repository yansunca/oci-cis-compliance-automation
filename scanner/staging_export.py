"""Export database staging JSONL rows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scanner.evidence import sha256_file


@dataclass(frozen=True)
class StagingExportFiles:
    """Paths for generated staging JSONL files."""

    scan_run: Path
    scan_file: Path
    canonical_finding_stage: Path

    @property
    def paths(self) -> tuple[Path, Path, Path]:
        return (self.scan_run, self.scan_file, self.canonical_finding_stage)


def write_staging_exports(
    staging_dir: Path,
    manifest: dict[str, Any],
    manifest_path: Path,
    canonical_findings_path: Path,
) -> StagingExportFiles:
    """Write database staging JSONL rows from wrapper artifacts."""

    staging_dir.mkdir(parents=True, exist_ok=True)
    files = StagingExportFiles(
        scan_run=staging_dir / "scan_run.jsonl",
        scan_file=staging_dir / "scan_file.jsonl",
        canonical_finding_stage=staging_dir / "canonical_finding_stage.jsonl",
    )
    _write_jsonl(files.scan_run, [_scan_run_row(manifest, manifest_path)])
    _write_jsonl(
        files.scan_file,
        [_scan_file_row(manifest, file_entry) for file_entry in manifest["files"]],
    )
    _write_jsonl(
        files.canonical_finding_stage,
        [_canonical_stage_row(finding) for finding in _read_jsonl(canonical_findings_path)],
    )
    return files


def _scan_run_row(manifest: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    return {
        "run_id": manifest["runId"],
        "tenancy_id": manifest["tenancyId"],
        "status": manifest["status"],
        "started_at": manifest["startedAt"],
        "completed_at": manifest.get("completedAt"),
        "scanner_version": manifest["scanner"].get("version"),
        "scanner_commit": manifest["scanner"].get("commit"),
        "wrapper_version": manifest["scanner"].get("wrapperVersion"),
        "benchmark_version": manifest["benchmark"].get("version"),
        "requested_regions_json": json.dumps(manifest["scope"]["requestedRegions"]),
        "completed_regions_json": json.dumps(manifest["scope"]["completedRegions"]),
        "manifest_checksum": "sha256:" + sha256_file(manifest_path),
    }


def _scan_file_row(manifest: dict[str, Any], file_entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": manifest["runId"],
        "source_path": file_entry["path"],
        "category": file_entry["category"],
        "file_format": file_entry["format"],
        "checksum": file_entry["checksum"],
        "size_bytes": file_entry["sizeBytes"],
        "row_count": file_entry.get("rowCount"),
        "schema_hash": file_entry.get("schemaHash"),
        "control_hint": file_entry.get("controlHint"),
        "required_for_completeness": "Y"
        if file_entry.get("requiredForCompleteness", True)
        else "N",
    }


def _canonical_stage_row(finding: dict[str, Any]) -> dict[str, Any]:
    source_lineage = finding["sourceLineage"]
    return {
        "run_id": source_lineage["runId"],
        "finding_id": finding["findingId"],
        "source_file": source_lineage["sourceFile"],
        "source_row": source_lineage["sourceRow"],
        "canonical_json": json.dumps(finding, sort_keys=True),
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
