#!/usr/bin/env python3
"""Build direct SQLcl load SQL for a validated downloaded real run package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, ROOT.as_posix())

from database.loader import build_load_plan  # noqa: E402


DEFAULT_RUN_DIR = Path("/tmp/oci-cis-runs/CIS-YYYYMMDDTHHMMSSZ")
DEFAULT_OUTPUT = Path("/tmp/oci-cis-adb-direct-load.sql")
MAX_SQL_CLOB_LITERAL_CHARS = 3000


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"expected JSON object in {path}")
            rows.append(row)
    return rows


def sql_literal(value: Any, *, clob: bool = False) -> str:
    if value is None:
        return "NULL"
    text = str(value)
    if clob:
        chunks = [
            _sql_text_literal(text[index : index + MAX_SQL_CLOB_LITERAL_CHARS])
            for index in range(0, len(text), MAX_SQL_CLOB_LITERAL_CHARS)
        ]
        if not chunks:
            chunks = [_sql_text_literal("")]
        return " || ".join(f"TO_CLOB({chunk})" for chunk in chunks)
    return _sql_text_literal(text)


def _sql_text_literal(text: str) -> str:
    delimiters = ("~", "!", "#", "^", "|", "`")
    for delimiter in delimiters:
        if delimiter not in text:
            return f"q'{delimiter}{text}{delimiter}'"
    escaped = text.replace("'", "''")
    return f"'{escaped}'"


def number_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    return str(value)


def timestamp_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    text = str(value).replace("Z", "+00:00")
    return f"TO_TIMESTAMP_TZ({sql_literal(text)}, 'YYYY-MM-DD\"T\"HH24:MI:SS.FFTZH:TZM')"


def build_sql(run_dir: Path, *, reconcile_absent: bool = True) -> str:
    plan = build_load_plan(run_dir)
    if not plan.validation.is_valid:
        raise ValueError("run is not valid for loading")

    scan_run_rows = read_jsonl(run_dir / "staging" / "scan_run.jsonl")
    scan_file_rows = read_jsonl(run_dir / "staging" / "scan_file.jsonl")
    config_rows = read_jsonl(run_dir / "config" / "config_version.jsonl")
    source_profile_rows = read_jsonl(run_dir / "config" / "source_profile.jsonl")
    field_alias_rows = read_jsonl(run_dir / "config" / "field_alias.jsonl")
    raw_rows = read_jsonl(run_dir / "raw" / "records-00001.jsonl")
    canonical_stage_rows = read_jsonl(run_dir / "staging" / "canonical_finding_stage.jsonl")
    run_id = scan_run_rows[0]["run_id"]
    config_ids = sorted({row["config_version_id"] for row in config_rows})

    lines = [
        f"-- Direct SQLcl load for {run_id}.",
        "-- Generated from validated local JSONL.",
        "set define off",
        "set sqlblanklines on",
        "whenever sqlerror exit sql.sqlcode rollback",
        "",
        "prompt Cleaning prior load if present",
        f"DELETE FROM cis_evidence_artifact_cache WHERE run_id = {sql_literal(run_id)};",
        f"DELETE FROM finding_observation WHERE run_id = {sql_literal(run_id)};",
        f"DELETE FROM canonical_finding_stage WHERE run_id = {sql_literal(run_id)};",
        f"DELETE FROM raw_cis_record WHERE run_id = {sql_literal(run_id)};",
        f"DELETE FROM scan_file WHERE run_id = {sql_literal(run_id)};",
        f"DELETE FROM scan_run WHERE run_id = {sql_literal(run_id)};",
        _delete_in("field_alias", "config_version_id", config_ids),
        _delete_in("source_profile", "config_version_id", config_ids),
        _delete_in("config_version", "config_version_id", config_ids),
        "COMMIT;",
        "",
    ]

    for row in scan_run_rows:
        lines.append(_insert_scan_run(row))
    for row in scan_file_rows:
        lines.append(_insert_scan_file(row))
    for row in config_rows:
        lines.append(_insert_config_version(row))
    for row in source_profile_rows:
        lines.append(_insert_source_profile(row))
    for row in field_alias_rows:
        lines.append(_insert_field_alias(row))
    for row in raw_rows:
        lines.append(_insert_raw_record(row))
    for row in canonical_stage_rows:
        lines.append(_insert_canonical_stage(row))

    lines.extend(
        [
            "prompt Running processing packages",
            "BEGIN",
            f"    canonical_finding_upsert.upsert_run({sql_literal(run_id)});",
            *(
                [f"    finding_absence_reconciliation.resolve_absent_for_run({sql_literal(run_id)});"]
                if reconcile_absent
                else [
                    "    -- Absence reconciliation intentionally skipped for this load.",
                    "    -- Use only for complete successful scans with a known full scope.",
                ]
            ),
            "    product_enrichment.enrich_all;",
            "END;",
            "/",
            "COMMIT;",
            "",
            "prompt Verifying loaded run",
            "SELECT run_id, status, file_count, raw_record_count, canonical_stage_count,",
            "       observation_count",
            "FROM vw_scan_run_health",
            f"WHERE run_id = {sql_literal(run_id)};",
            "SELECT current_state, priority, COUNT(*) AS finding_count",
            "FROM v_cis_current_findings",
            "GROUP BY current_state, priority",
            "ORDER BY current_state, priority;",
            "SELECT COUNT(*) AS work_queue_count",
            "FROM vw_finding_work_queue",
            f"WHERE last_observed_run_id = {sql_literal(run_id)};",
            "exit success",
            "",
        ],
    )
    return "\n".join(lines)


def _delete_in(table_name: str, column_name: str, values: Sequence[str]) -> str:
    if not values:
        return f"DELETE FROM {table_name} WHERE 1 = 0;"
    joined = ", ".join(sql_literal(value) for value in values)
    return f"DELETE FROM {table_name} WHERE {column_name} IN ({joined});"


def _insert_scan_run(row: dict[str, Any]) -> str:
    return _insert(
        "scan_run",
        (
            "run_id",
            "tenancy_id",
            "status",
            "started_at",
            "completed_at",
            "scanner_version",
            "scanner_commit",
            "wrapper_version",
            "benchmark_version",
            "requested_regions_json",
            "completed_regions_json",
            "manifest_checksum",
        ),
        (
            sql_literal(row["run_id"]),
            sql_literal(row["tenancy_id"]),
            sql_literal(row["status"]),
            timestamp_literal(row["started_at"]),
            timestamp_literal(row.get("completed_at")),
            sql_literal(row.get("scanner_version")),
            sql_literal(row.get("scanner_commit")),
            sql_literal(row.get("wrapper_version")),
            sql_literal(row.get("benchmark_version")),
            sql_literal(row.get("requested_regions_json"), clob=True),
            sql_literal(row.get("completed_regions_json"), clob=True),
            sql_literal(row.get("manifest_checksum")),
        ),
    )


def _insert_scan_file(row: dict[str, Any]) -> str:
    return _insert(
        "scan_file",
        (
            "run_id",
            "source_path",
            "category",
            "file_format",
            "checksum",
            "size_bytes",
            "row_count",
            "schema_hash",
            "control_hint",
            "required_for_completeness",
        ),
        (
            sql_literal(row["run_id"]),
            sql_literal(row["source_path"]),
            sql_literal(row["category"]),
            sql_literal(row["file_format"]),
            sql_literal(row["checksum"]),
            number_literal(row["size_bytes"]),
            number_literal(row.get("row_count")),
            sql_literal(row.get("schema_hash")),
            sql_literal(row.get("control_hint")),
            sql_literal(row["required_for_completeness"]),
        ),
    )


def _insert_config_version(row: dict[str, Any]) -> str:
    return _insert(
        "config_version",
        ("config_version_id", "status", "description"),
        (
            sql_literal(row["config_version_id"]),
            sql_literal(row["status"]),
            sql_literal(row.get("description")),
        ),
    )


def _insert_source_profile(row: dict[str, Any]) -> str:
    return _insert(
        "source_profile",
        (
            "source_profile_id",
            "config_version_id",
            "display_name",
            "schema_hash",
            "required_headers_json",
        ),
        (
            sql_literal(row["source_profile_id"]),
            sql_literal(row["config_version_id"]),
            sql_literal(row["display_name"]),
            sql_literal(row["schema_hash"]),
            sql_literal(row["required_headers_json"], clob=True),
        ),
    )


def _insert_field_alias(row: dict[str, Any]) -> str:
    return _insert(
        "field_alias",
        ("source_profile_id", "config_version_id", "source_header", "canonical_header"),
        (
            sql_literal(row["source_profile_id"]),
            sql_literal(row["config_version_id"]),
            sql_literal(row["source_header"]),
            sql_literal(row["canonical_header"]),
        ),
    )


def _insert_raw_record(row: dict[str, Any]) -> str:
    return (
        "INSERT INTO raw_cis_record (run_id, scan_file_id, source_row, schema_hash, "
        "payload_json, record_checksum)\n"
        "SELECT "
        f"{sql_literal(row['run_id'])}, scan_file.scan_file_id, "
        f"{number_literal(row['source_row'])}, {sql_literal(row['schema_hash'])}, "
        f"{sql_literal(row['payload_json'], clob=True)}, {sql_literal(row['record_checksum'])}\n"
        "FROM scan_file\n"
        f"WHERE scan_file.run_id = {sql_literal(row['run_id'])}\n"
        f"AND scan_file.source_path = {sql_literal(row['scan_file_path'])};"
    )


def _insert_canonical_stage(row: dict[str, Any]) -> str:
    return _insert(
        "canonical_finding_stage",
        ("run_id", "finding_id", "source_file", "source_row", "canonical_json"),
        (
            sql_literal(row["run_id"]),
            sql_literal(row["finding_id"]),
            sql_literal(row["source_file"]),
            number_literal(row["source_row"]),
            sql_literal(row["canonical_json"], clob=True),
        ),
    )


def _insert(table_name: str, columns: Sequence[str], values: Sequence[str]) -> str:
    column_list = ", ".join(columns)
    value_list = ", ".join(values)
    return f"INSERT INTO {table_name} ({column_list}) VALUES ({value_list});"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, default=DEFAULT_RUN_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--skip-absence-reconciliation",
        action="store_true",
        help=(
            "Skip marking previously open findings resolved. Use this for imported native "
            "report bundles or partial scans; keep the default for complete scheduled scans."
        ),
    )
    args = parser.parse_args(argv)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        build_sql(args.run_dir, reconcile_absent=not args.skip_absence_reconciliation),
        encoding="utf-8",
    )
    print(json.dumps({"output": args.output.as_posix()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
