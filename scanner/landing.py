"""CSV-to-landing JSONL conversion."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from scanner.source_contract import normalized_schema_hash


@dataclass(frozen=True)
class LandingConversionResult:
    """Result metadata for a CSV-to-JSONL conversion."""

    record_count: int
    schema_hash: str


def csv_to_landing_jsonl(
    *,
    source_csv: Path,
    output_jsonl: Path,
    run_id: str,
    scanner_version: str,
    benchmark_version: str,
    control_hint: str | None,
    recorded_at: str | None,
    source_profile_id: str | None = None,
) -> LandingConversionResult:
    """Stream a CSV file into generic landing-record JSONL."""

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    if b"\x00" in source_csv.read_bytes():
        raise ValueError(f"malformed CSV: {source_csv} contains NUL bytes")
    with source_csv.open("r", encoding="utf-8", newline="") as source_handle:
        reader = csv.DictReader(source_handle)
        headers = reader.fieldnames or []
        if not headers:
            raise ValueError(f"malformed CSV: {source_csv} has no header row")
        schema_hash = normalized_schema_hash(headers)
        count = 0
        with output_jsonl.open("w", encoding="utf-8") as output_handle:
            for count, row in enumerate(reader, start=1):
                if None in row:
                    raise ValueError(f"malformed CSV: {source_csv} row {count} has extra columns")
                record = {
                    "contractVersion": "1.0",
                    "runId": run_id,
                    "sourceFile": source_csv.name,
                    "sourceObjectUri": None,
                    "sourceChecksum": None,
                    "sourceRow": count,
                    "schemaHash": schema_hash,
                    "scannerVersion": scanner_version,
                    "benchmarkVersion": benchmark_version,
                    "controlHint": control_hint,
                    "sourceProfileId": source_profile_id,
                    "recordedAt": recorded_at,
                    "payload": dict(row),
                }
                output_handle.write(json.dumps(record, sort_keys=True) + "\n")
    return LandingConversionResult(record_count=count, schema_hash=schema_hash)
