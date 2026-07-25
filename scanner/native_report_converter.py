"""Convert native OCI CIS report folders into app run packages."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scanner.config_seed import write_config_seed
from scanner.evidence import build_file_manifest, build_manifest, build_run_ready, sha256_file
from scanner.operational_log import make_log_event
from scanner.run_layout import RunLayout, build_run_layout
from scanner.source_contract import normalized_schema_hash
from scanner.staging_export import write_staging_exports

NATIVE_CONVERTER_VERSION = "native-report-converter-0.1.0"
CONFIGURATION_VERSION = "source-contract-v1"


def _raise_csv_field_limit() -> None:
    limit = sys.maxsize
    while True:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 10


_raise_csv_field_limit()


@dataclass(frozen=True)
class NativeReportConversionResult:
    """Result from converting one native CIS report folder."""

    status: str
    layout: RunLayout
    landing_record_count: int
    canonical_finding_count: int
    native_error_count: int
    error_message: str | None


@dataclass(frozen=True)
class SummaryRow:
    """One recommendation row from the native CIS summary CSV."""

    recommendation: str
    section: str
    level: str | None
    compliant: str
    findings: str | None
    compliant_items: str | None
    total: str | None
    compliance_percentage: str | None
    title: str
    cis_v8: str | None
    cccs_guard_rail: str | None
    regions: list[str]
    filename: str | None
    remediation: str | None
    extract_date: str | None


def convert_native_report_run(
    *,
    native_report_dir: Path,
    output_root: Path,
    run_id: str,
    tenancy_id: str,
    started_at: str | None = None,
    completed_at: str | None = None,
    scanner_version: str = "UNKNOWN",
    scanner_commit: str = "UNKNOWN",
    scanner_source_checksum: str | None = None,
    scanner_image_digest: str = "UNKNOWN",
    benchmark_version: str | None = None,
    benchmark_level: str = "2",
    requested_regions: list[str] | None = None,
    completed_regions: list[str] | None = None,
    source_object_uri_prefix: str | None = None,
) -> NativeReportConversionResult:
    """Convert a native upstream CIS report folder into the app run layout."""

    if not native_report_dir.is_dir():
        raise ValueError(f"native report directory not found: {native_report_dir}")

    run_dir = output_root / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    layout = build_run_layout(output_root, run_id)
    effective_completed_at = _coerce_datetime(completed_at) or _extract_completed_at(
        native_report_dir,
    )
    effective_started_at = _coerce_datetime(started_at) or effective_completed_at
    logs: list[dict[str, Any]] = [
        make_log_event(
            level="INFO",
            component="native-report-converter",
            event_type="RUN_STARTED",
            message="Native CIS report conversion started",
            timestamp=effective_started_at,
            run_id=run_id,
        ),
    ]

    try:
        copied_files = _copy_native_files(native_report_dir, layout)
        summary_path = _find_required(copied_files, pattern=r"(?:^|_)cis_summary_report\.csv$")
        error_path = _find_optional(copied_files, pattern=r"(?:^|_)error_report\.csv$")
        html_path = _find_optional(copied_files, pattern=r"(?:^|_)cis_summary_report\.html$")
        summary_rows = _read_summary_rows(summary_path)
        summary_by_control = {
            row.recommendation: row for row in summary_rows if row.recommendation
        }
        native_error_count = _count_csv_rows(error_path) if error_path else 0
        effective_benchmark_version = (
            benchmark_version
            or _extract_benchmark_version(html_path)
            or "UNKNOWN"
        )
        effective_regions = _regions_from_summary(summary_rows)
        effective_requested_regions = requested_regions or effective_regions or ["UNKNOWN"]
        effective_completed_regions = completed_regions or effective_regions or ["UNKNOWN"]
        file_entries = [
            build_file_manifest(path, root=layout.run_dir, category=_category(path))
            for path in copied_files
        ]
        landing_count, canonical_count = _write_records(
            layout=layout,
            run_id=run_id,
            tenancy_id=tenancy_id,
            scanner_version=scanner_version,
            benchmark_version=effective_benchmark_version,
            recorded_at=effective_completed_at,
            summary_rows=summary_rows,
            summary_by_control=summary_by_control,
            copied_files=copied_files,
            source_object_uri_prefix=source_object_uri_prefix,
            html_report=html_path,
            summary_report=summary_path,
            error_report=error_path,
        )
        config_seed_files = write_config_seed(layout.config_dir)
        logs.append(
            make_log_event(
                level="INFO",
                component="native-report-converter",
                event_type="LANDING_WRITTEN",
                message="Native CIS landing records written",
                timestamp=effective_completed_at,
                run_id=run_id,
                source_file="landing/records-00001.jsonl",
                extra={
                    "canonical_finding_count": canonical_count,
                    "native_error_count": native_error_count,
                    "record_count": landing_count,
                },
            ),
        )
        log_path = _write_logs(layout, logs)
        file_entries.extend(
            [
                build_file_manifest(
                    layout.landing_dir / "records-00001.jsonl",
                    root=layout.run_dir,
                    category="LANDING",
                ),
                build_file_manifest(
                    layout.raw_dir / "records-00001.jsonl",
                    root=layout.run_dir,
                    category="METADATA",
                ),
                build_file_manifest(
                    layout.canonical_dir / "findings-00001.jsonl",
                    root=layout.run_dir,
                    category="METADATA",
                ),
                build_file_manifest(
                    layout.reports_dir / "cis-audit-summary.jsonl",
                    root=layout.run_dir,
                    category="SUMMARY",
                ),
                *[
                    build_file_manifest(path, root=layout.run_dir, category="METADATA")
                    for path in config_seed_files.paths
                ],
                build_file_manifest(log_path, root=layout.run_dir, category="LOG"),
            ],
        )
        manifest = build_manifest(
            run_id=run_id,
            tenancy_id=tenancy_id,
            started_at=effective_started_at,
            completed_at=effective_completed_at,
            scanner={
                "name": "oci-cis-landingzone-quickstart/scripts/cis_reports.py",
                "version": scanner_version,
                "commit": scanner_commit,
                "sourceChecksum": scanner_source_checksum,
                "wrapperVersion": NATIVE_CONVERTER_VERSION,
                "imageDigest": scanner_image_digest,
                "ociSdkVersion": None,
                "pythonVersion": None,
            },
            benchmark={
                "name": "CIS OCI Foundations Benchmark",
                "version": effective_benchmark_version,
                "level": benchmark_level,
                "includesOracleBestPractices": False,
            },
            requested_regions=effective_requested_regions,
            completed_regions=effective_completed_regions,
            files=file_entries,
        )
        manifest["metadata"] = {
            "converter": NATIVE_CONVERTER_VERSION,
            "nativeErrorRowCount": native_error_count,
            "nativeHtmlSummary": _relative_or_none(html_path, layout.run_dir),
            "nativeSummaryCsv": summary_path.relative_to(layout.run_dir).as_posix(),
            "nativeErrorCsv": _relative_or_none(error_path, layout.run_dir),
            "statusMeaning": (
                "Native report bundle converted; native errors are retained as audit evidence."
            ),
        }
        manifest["errors"] = _manifest_errors(error_path)
        _write_json(layout.manifest_path, manifest)
        write_staging_exports(
            layout.staging_dir,
            manifest,
            layout.manifest_path,
            layout.canonical_dir / "findings-00001.jsonl",
        )
        run_ready = build_run_ready(
            run_id=run_id,
            manifest_path=layout.manifest_path.name,
            manifest_checksum="sha256:" + sha256_file(layout.manifest_path),
            published_at=effective_completed_at,
            landing_file_count=1,
            landing_record_count=landing_count,
            requested_regions=effective_requested_regions,
            completed_regions=effective_completed_regions,
        )
        _write_json(layout.run_ready_path, run_ready)
        layout.success_marker.write_text("SUCCESS\n", encoding="utf-8")
        return NativeReportConversionResult(
            status="SUCCESS",
            layout=layout,
            landing_record_count=landing_count,
            canonical_finding_count=canonical_count,
            native_error_count=native_error_count,
            error_message=None,
        )
    except Exception as exc:  # noqa: BLE001 - converter must publish failure marker.
        logs.append(
            make_log_event(
                level="ERROR",
                component="native-report-converter",
                event_type="RUN_FAILED",
                message=str(exc),
                timestamp=effective_completed_at,
                run_id=run_id,
                extra={"error_code": type(exc).__name__},
            ),
        )
        _write_logs(layout, logs)
        layout.failed_marker.write_text("FAILED\n", encoding="utf-8")
        if layout.run_ready_path.exists():
            layout.run_ready_path.unlink()
        if layout.success_marker.exists():
            layout.success_marker.unlink()
        return NativeReportConversionResult(
            status="FAILED",
            layout=layout,
            landing_record_count=0,
            canonical_finding_count=0,
            native_error_count=0,
            error_message=str(exc),
        )


def _copy_native_files(native_report_dir: Path, layout: RunLayout) -> list[Path]:
    copied: list[Path] = []
    for source_path in sorted(native_report_dir.iterdir()):
        if not source_path.is_file() or source_path.name == ".DS_Store":
            continue
        target = layout.reports_dir / source_path.name
        shutil.copy2(source_path, target)
        copied.append(target)
    if not copied:
        raise ValueError(f"no native report files found in {native_report_dir}")
    return copied


def _write_records(
    *,
    layout: RunLayout,
    run_id: str,
    tenancy_id: str,
    scanner_version: str,
    benchmark_version: str,
    recorded_at: str,
    summary_rows: list[SummaryRow],
    summary_by_control: dict[str, SummaryRow],
    copied_files: list[Path],
    source_object_uri_prefix: str | None,
    html_report: Path | None,
    summary_report: Path,
    error_report: Path | None,
) -> tuple[int, int]:
    landing_path = layout.landing_dir / "records-00001.jsonl"
    raw_path = layout.raw_dir / "records-00001.jsonl"
    canonical_path = layout.canonical_dir / "findings-00001.jsonl"
    audit_summary_path = layout.reports_dir / "cis-audit-summary.jsonl"
    for path in (landing_path, raw_path, canonical_path, audit_summary_path):
        path.write_text("", encoding="utf-8")

    product_by_compartment = _compartment_product_map(copied_files)
    landing_count = 0
    canonical_count = 0
    controls_with_detail_findings: set[str] = set()
    with landing_path.open("a", encoding="utf-8") as landing_handle:
        with raw_path.open("a", encoding="utf-8") as raw_handle:
            with canonical_path.open("a", encoding="utf-8") as canonical_handle:
                for detail_path in _detail_csvs(copied_files):
                    control_hint = _control_hint(detail_path)
                    summary = summary_by_control.get(control_hint or "")
                    headers, rows = _read_csv_dicts(detail_path)
                    schema_hash = normalized_schema_hash(headers)
                    report_links = _report_links(
                        source_object_uri_prefix=source_object_uri_prefix,
                        html_report=html_report,
                        summary_report=summary_report,
                        detail_report=detail_path,
                        error_report=error_report,
                    )
                    for source_row, payload in enumerate(rows, start=1):
                        landing_record = _landing_record(
                            run_id=run_id,
                            source_path=detail_path,
                            source_row=source_row,
                            schema_hash=schema_hash,
                            scanner_version=scanner_version,
                            benchmark_version=benchmark_version,
                            control_hint=control_hint,
                            recorded_at=recorded_at,
                            payload=payload,
                            source_object_uri_prefix=source_object_uri_prefix,
                        )
                        landing_handle.write(json.dumps(landing_record, sort_keys=True) + "\n")
                        raw_handle.write(
                            json.dumps(
                                _raw_record(
                                    landing_record=landing_record,
                                    run_id=run_id,
                                    scan_file_path=detail_path.relative_to(
                                        layout.run_dir,
                                    ).as_posix(),
                                    schema_hash=schema_hash,
                                ),
                                sort_keys=True,
                            )
                            + "\n",
                        )
                        finding = _canonical_finding(
                            landing_record=landing_record,
                            tenancy_id=tenancy_id,
                            benchmark_version=benchmark_version,
                            summary=summary,
                            report_links=report_links,
                            product_by_compartment=product_by_compartment,
                        )
                        canonical_handle.write(json.dumps(finding, sort_keys=True) + "\n")
                        landing_count += 1
                        canonical_count += 1
                        if control_hint:
                            controls_with_detail_findings.add(control_hint)

                for source_row, summary in enumerate(summary_rows, start=1):
                    _append_audit_summary(
                        audit_summary_path,
                        summary=summary,
                        run_id=run_id,
                        benchmark_version=benchmark_version,
                        source_row=source_row,
                        report_links=_report_links(
                            source_object_uri_prefix=source_object_uri_prefix,
                            html_report=html_report,
                            summary_report=summary_report,
                            detail_report=_detail_path_for_summary(copied_files, summary),
                            error_report=error_report,
                        ),
                    )
                    if summary.compliant != "No":
                        continue
                    if summary.recommendation in controls_with_detail_findings:
                        continue
                    landing_record = _summary_landing_record(
                        run_id=run_id,
                        source_path=summary_report,
                        source_row=source_row,
                        scanner_version=scanner_version,
                        benchmark_version=benchmark_version,
                        recorded_at=recorded_at,
                        summary=summary,
                        source_object_uri_prefix=source_object_uri_prefix,
                    )
                    landing_handle.write(json.dumps(landing_record, sort_keys=True) + "\n")
                    raw_handle.write(
                        json.dumps(
                            _raw_record(
                                landing_record=landing_record,
                                run_id=run_id,
                                scan_file_path=summary_report.relative_to(
                                    layout.run_dir,
                                ).as_posix(),
                                schema_hash=landing_record["schemaHash"],
                            ),
                            sort_keys=True,
                        )
                        + "\n",
                    )
                    finding = _canonical_finding(
                        landing_record=landing_record,
                        tenancy_id=tenancy_id,
                        benchmark_version=benchmark_version,
                        summary=summary,
                        report_links=_report_links(
                            source_object_uri_prefix=source_object_uri_prefix,
                            html_report=html_report,
                            summary_report=summary_report,
                            detail_report=None,
                            error_report=error_report,
                        ),
                        product_by_compartment=product_by_compartment,
                    )
                    canonical_handle.write(json.dumps(finding, sort_keys=True) + "\n")
                    landing_count += 1
                    canonical_count += 1
    return landing_count, canonical_count


def _read_summary_rows(path: Path) -> list[SummaryRow]:
    rows: list[SummaryRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows.append(
                SummaryRow(
                    recommendation=_clean(row.get("Recommendation #")) or "",
                    section=_clean(row.get("Section")) or "Unknown",
                    level=_clean(row.get("Level")),
                    compliant=_clean(row.get("Compliant")) or "Unknown",
                    findings=_clean(row.get("Findings")),
                    compliant_items=_clean(row.get("Compliant Items")),
                    total=_clean(row.get("Total")),
                    compliance_percentage=_clean(
                        row.get("Compliance Percentage Per Recommendation"),
                    ),
                    title=_clean(row.get("Title")) or "Untitled CIS recommendation",
                    cis_v8=_clean(row.get("CIS v8")),
                    cccs_guard_rail=_clean(row.get("CCCS Guard Rail")),
                    regions=_parse_regions(row.get("Regions")),
                    filename=_clean(row.get("Filename")),
                    remediation=_clean(row.get("Remediation")),
                    extract_date=_coerce_datetime(row.get("extract_date")),
                ),
            )
    if not rows:
        raise ValueError(f"summary CSV has no rows: {path}")
    return rows


def _read_csv_dicts(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        if not headers:
            raise ValueError(f"CSV has no header row: {path}")
        rows: list[dict[str, str]] = []
        for line_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(
                    f"malformed CSV row {line_number} in {path.name}: extra columns",
                )
            rows.append(dict(row))
        return headers, rows


def _landing_record(
    *,
    run_id: str,
    source_path: Path,
    source_row: int,
    schema_hash: str,
    scanner_version: str,
    benchmark_version: str,
    control_hint: str | None,
    recorded_at: str,
    payload: dict[str, str],
    source_object_uri_prefix: str | None,
) -> dict[str, Any]:
    return {
        "contractVersion": "1.0",
        "runId": run_id,
        "sourceFile": source_path.name,
        "sourceObjectUri": _source_uri(source_object_uri_prefix, source_path),
        "sourceChecksum": "sha256:" + sha256_file(source_path),
        "sourceRow": source_row,
        "schemaHash": schema_hash,
        "scannerVersion": scanner_version,
        "benchmarkVersion": benchmark_version,
        "controlHint": control_hint,
        "sourceProfileId": "native-cis-detail",
        "recordedAt": recorded_at,
        "payload": payload,
    }


def _summary_landing_record(
    *,
    run_id: str,
    source_path: Path,
    source_row: int,
    scanner_version: str,
    benchmark_version: str,
    recorded_at: str,
    summary: SummaryRow,
    source_object_uri_prefix: str | None,
) -> dict[str, Any]:
    payload = {
        "Recommendation #": summary.recommendation,
        "Section": summary.section,
        "Level": summary.level,
        "Compliant": summary.compliant,
        "Findings": summary.findings,
        "Compliant Items": summary.compliant_items,
        "Total": summary.total,
        "Compliance Percentage Per Recommendation": summary.compliance_percentage,
        "Title": summary.title,
        "CIS v8": summary.cis_v8,
        "CCCS Guard Rail": summary.cccs_guard_rail,
        "Regions": json.dumps(summary.regions),
        "Filename": summary.filename,
        "Remediation": summary.remediation,
        "extract_date": summary.extract_date,
    }
    headers = list(payload)
    return _landing_record(
        run_id=run_id,
        source_path=source_path,
        source_row=source_row,
        schema_hash=normalized_schema_hash(headers),
        scanner_version=scanner_version,
        benchmark_version=benchmark_version,
        control_hint=summary.recommendation,
        recorded_at=recorded_at,
        payload=payload,
        source_object_uri_prefix=source_object_uri_prefix,
    ) | {"sourceProfileId": "native-cis-summary"}



def _compartment_product_map(copied_files: list[Path]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    compartment_file = next((path for path in copied_files if path.name == "raw_data_identity_compartments.csv"), None)
    if compartment_file is None or not compartment_file.exists():
        return result

    _, rows = _read_csv_dicts(compartment_file)
    for row in rows:
        compartment_id = _blank_to_none(row.get("id"))
        if not compartment_id:
            continue
        defined_tags = _parse_tag_dict(row.get("defined_tags"))
        operations = defined_tags.get("Operations") if isinstance(defined_tags, dict) else None
        product_id = None
        if isinstance(operations, dict):
            product_id = _blank_to_none(operations.get("ProductId"))
        result[compartment_id] = {
            "name": _blank_to_none(row.get("name")),
            "path": f"/{_blank_to_none(row.get('name')) or compartment_id}",
            "parentOcid": _blank_to_none(row.get("compartment_id")),
            "productId": product_id,
            "tagNamespace": "Operations" if product_id else None,
            "tagKey": "ProductId" if product_id else None,
            "tagValue": product_id,
        }
    return result


def _parse_tag_dict(value: Any) -> dict[str, Any]:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    text = str(value).strip()
    if not text or text == "{}":
        return {}
    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _product_for_compartment(compartment_meta: dict[str, Any]) -> dict[str, Any]:
    product_id = _blank_to_none(compartment_meta.get("productId"))
    if not product_id:
        return {
            "productId": "UNASSIGNED",
            "displayName": "Unassigned",
            "mappingSource": "UNASSIGNED",
            "sourceCompartmentOcid": None,
            "tagNamespace": "Operations",
            "tagKey": "ProductId",
            "tagValue": None,
        }
    return {
        "productId": product_id,
        "displayName": product_id,
        "mappingSource": "COMPARTMENT_TAG",
        "sourceCompartmentOcid": None,
        "tagNamespace": compartment_meta.get("tagNamespace") or "Operations",
        "tagKey": compartment_meta.get("tagKey") or "ProductId",
        "tagValue": compartment_meta.get("tagValue") or product_id,
    }

def _canonical_finding(
    *,
    landing_record: dict[str, Any],
    tenancy_id: str,
    benchmark_version: str,
    summary: SummaryRow | None,
    report_links: dict[str, str | None],
    product_by_compartment: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = landing_record["payload"]
    control_id = str(landing_record.get("controlHint") or "UNKNOWN")
    region = _blank_to_none(payload.get("region")) or _first_region(summary)
    resource_key = _first_present(payload, ("id", "name", "display_name"))
    compartment_id = _first_present(payload, ("compartment_id",)) or tenancy_id
    compartment_meta = (product_by_compartment or {}).get(compartment_id, {})
    product = _product_for_compartment(compartment_meta)
    scope_type = "RESOURCE" if resource_key else ("REGION" if region else "TENANCY")
    scope_key = resource_key or region or tenancy_id
    title = summary.title if summary else f"OCI CIS control {control_id}"
    section = summary.section if summary else "Unknown"
    cis_level = summary.level if summary else None
    finding_id = _stable_finding_id(
        tenancy_id=tenancy_id,
        benchmark_version=benchmark_version,
        control_display_id=control_id,
        scope_type=scope_type,
        scope_key=scope_key,
        region=region,
    )
    resource_type = _resource_type_from_file(landing_record["sourceFile"])
    return {
        "contractVersion": "1.0",
        "findingId": finding_id,
        "tenancyId": tenancy_id,
        "control": {
            "lineageId": f"cis-oci-{benchmark_version}-{control_id}",
            "displayId": control_id,
            "title": title,
            "section": section,
            "cisLevel": cis_level,
            "benchmarkVersion": benchmark_version,
        },
        "scope": {"type": scope_type, "key": scope_key, "region": region},
        "resource": {
            "key": resource_key,
            "ocid": resource_key if resource_key and resource_key.startswith("ocid1.") else None,
            "name": _blank_to_none(payload.get("display_name") or payload.get("name")),
            "type": resource_type,
            "region": region,
            "lifecycleState": _blank_to_none(payload.get("lifecycle_state")),
        }
        if resource_key
        else None,
        "compartment": {
            "ocid": compartment_id,
            "name": compartment_meta.get("name") or compartment_id,
            "path": compartment_meta.get("path") or f"/{compartment_id}",
            "parentOcid": compartment_meta.get("parentOcid"),
        },
        "product": product,
        "state": "NEW",
        "priority": _priority(summary),
        "riskScore": _risk_score(summary),
        "owner": None,
        "firstSeenAt": landing_record["recordedAt"],
        "lastSeenAt": landing_record["recordedAt"],
        "lastStateChangeAt": landing_record["recordedAt"],
        "resolvedAt": None,
        "dueAt": None,
        "evidenceSummary": _evidence_summary(summary, payload),
        "remediation": summary.remediation if summary else None,
        "externalReference": None,
        "sourceLineage": {
            "runId": landing_record["runId"],
            "sourceObjectUri": landing_record.get("sourceObjectUri"),
            "sourceFile": landing_record["sourceFile"],
            "sourceRow": landing_record["sourceRow"],
            "schemaHash": landing_record["schemaHash"],
            "scannerVersion": landing_record["scannerVersion"],
            "benchmarkVersion": benchmark_version,
            "wrapperVersion": NATIVE_CONVERTER_VERSION,
            "normalizerVersion": NATIVE_CONVERTER_VERSION,
            "configurationVersion": CONFIGURATION_VERSION,
        },
        "attributes": {
            "sourceProfileId": landing_record.get("sourceProfileId"),
            "nativeReportLinks": report_links,
            "cisAudit": _cis_audit_attributes(summary),
        },
    }


def _append_audit_summary(
    path: Path,
    *,
    summary: SummaryRow,
    run_id: str,
    benchmark_version: str,
    source_row: int,
    report_links: dict[str, str | None],
) -> None:
    record = {
        "runId": run_id,
        "benchmarkVersion": benchmark_version,
        "sourceRow": source_row,
        "recommendation": summary.recommendation,
        "section": summary.section,
        "level": summary.level,
        "result": summary.compliant,
        "findings": summary.findings,
        "compliantItems": summary.compliant_items,
        "total": summary.total,
        "compliancePercentage": summary.compliance_percentage,
        "title": summary.title,
        "remediation": summary.remediation,
        "regions": summary.regions,
        "nativeFilename": summary.filename,
        "reportLinks": report_links,
        "extractDate": summary.extract_date,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _raw_record(
    *,
    landing_record: dict[str, Any],
    run_id: str,
    scan_file_path: str,
    schema_hash: str,
) -> dict[str, Any]:
    payload_json = json.dumps(landing_record["payload"], sort_keys=True)
    checksum_material = "|".join(
        [run_id, scan_file_path, str(landing_record["sourceRow"]), schema_hash, payload_json],
    )
    return {
        "run_id": run_id,
        "scan_file_path": scan_file_path,
        "source_row": landing_record["sourceRow"],
        "schema_hash": schema_hash,
        "payload_json": payload_json,
        "record_checksum": "sha256:"
        + hashlib.sha256(checksum_material.encode("utf-8")).hexdigest(),
    }


def _find_required(paths: list[Path], *, pattern: str) -> Path:
    found = _find_optional(paths, pattern=pattern)
    if found is None:
        raise ValueError(f"required native report not found: {pattern}")
    return found


def _find_optional(paths: list[Path], *, pattern: str) -> Path | None:
    regex = re.compile(pattern)
    matches = [path for path in paths if regex.search(path.name)]
    if len(matches) > 1:
        raise ValueError(f"multiple native reports matched {pattern}: {matches}")
    return matches[0] if matches else None


def _detail_csvs(paths: list[Path]) -> list[Path]:
    return [
        path
        for path in sorted(paths)
        if path.suffix.lower() == ".csv"
        and (path.name.startswith("cis_") or "_cis_" in path.name)
        and "cis_summary_report" not in path.name
        and "error_report" not in path.name
    ]


def _category(path: Path) -> str:
    if path.suffix.lower() == ".html":
        return "REPORT"
    if "summary_report" in path.name:
        return "SUMMARY"
    if "error_report" in path.name:
        return "METADATA"
    if path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
        return "REPORT"
    if (path.name.startswith("cis_") or "_cis_" in path.name) and path.suffix.lower() == ".csv":
        return "DETAIL"
    return "OTHER"


def _format_for_native_link(path: Path | None) -> str | None:
    if path is None:
        return None
    return path.name


def _report_links(
    *,
    source_object_uri_prefix: str | None,
    html_report: Path | None,
    summary_report: Path,
    detail_report: Path | None,
    error_report: Path | None,
) -> dict[str, str | None]:
    return {
        "nativeHtmlSummary": _source_uri(source_object_uri_prefix, html_report)
        or _format_for_native_link(html_report),
        "nativeSummaryCsv": _source_uri(source_object_uri_prefix, summary_report)
        or summary_report.name,
        "nativeDetailCsv": _source_uri(source_object_uri_prefix, detail_report)
        or _format_for_native_link(detail_report),
        "nativeErrorCsv": _source_uri(source_object_uri_prefix, error_report)
        or _format_for_native_link(error_report),
    }


def _detail_path_for_summary(paths: list[Path], summary: SummaryRow) -> Path | None:
    if not summary.filename:
        return None
    for path in paths:
        if path.name == summary.filename:
            return path
    return None


def _source_uri(prefix: str | None, path: Path | None) -> str | None:
    if not prefix or path is None:
        return None
    return prefix.rstrip("/") + "/" + path.name


def _control_hint(path: Path) -> str | None:
    match = re.search(r"_(\d+(?:-\d+)+)\.csv$", path.name)
    return match.group(1).replace("-", ".") if match else None


def _resource_type_from_file(filename: str) -> str:
    if "_cis_" in filename:
        middle = filename.split("_cis_", 1)[1].rsplit("_", 1)[0]
    elif filename.startswith("cis_"):
        middle = filename.split("cis_", 1)[1].rsplit("_", 1)[0]
    else:
        return "native-cis-summary"
    return re.sub(r"[^a-z0-9]+", "-", middle.lower()).strip("-") or "native-cis-detail"


def _parse_regions(value: str | None) -> list[str]:
    cleaned = _clean(value)
    if not cleaned:
        return []
    try:
        parsed = ast.literal_eval(cleaned)
    except (SyntaxError, ValueError):
        parsed = None
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item).strip()]
    return [part.strip() for part in cleaned.split(",") if part.strip()]


def _regions_from_summary(rows: list[SummaryRow]) -> list[str]:
    regions: list[str] = []
    for row in rows:
        for region in row.regions:
            if region not in regions:
                regions.append(region)
    return regions


def _extract_completed_at(native_report_dir: Path) -> str:
    summary = _find_optional(
        list(native_report_dir.iterdir()),
        pattern=r"(?:^|_)cis_summary_report\.csv$",
    )
    if summary:
        try:
            rows = _read_summary_rows(summary)
        except ValueError:
            rows = []
        for row in rows:
            if row.extract_date:
                return row.extract_date
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _extract_benchmark_version(html_path: Path | None) -> str | None:
    if html_path is None:
        return None
    text = html_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"Benchmark\s+([0-9]+(?:\.[0-9]+)+)", text)
    return match.group(1) if match else None


def _manifest_errors(error_path: Path | None) -> list[dict[str, Any]]:
    if error_path is None:
        return []
    _, rows = _read_csv_dicts(error_path)
    return [
        {
            "code": str(row.get("id") or "NATIVE_REPORT_ERROR")[:255],
            "message": str(row.get("error") or "Native report error")[:3500],
            "component": "cis_reports.py",
            "region": None,
            "service": None,
            "fatal": False,
        }
        for row in rows
    ]


def _count_csv_rows(path: Path | None) -> int:
    if path is None:
        return 0
    _, rows = _read_csv_dicts(path)
    return len(rows)


def _priority(summary: SummaryRow | None) -> str:
    if summary is None:
        return "INFORMATIONAL"
    if summary.level == "2":
        return "HIGH"
    if summary.level == "1":
        return "MEDIUM"
    return "LOW"


def _risk_score(summary: SummaryRow | None) -> int:
    if summary is None:
        return 0
    if summary.level == "2":
        return 75
    if summary.level == "1":
        return 50
    return 25


def _evidence_summary(summary: SummaryRow | None, payload: dict[str, str]) -> str:
    name = _first_present(payload, ("display_name", "name", "id")) or "scope-level finding"
    if summary is None:
        return f"Native OCI CIS detail row observed for {name}."
    return f"CIS {summary.recommendation} reported {summary.compliant} for {name}."


def _cis_audit_attributes(summary: SummaryRow | None) -> dict[str, Any]:
    if summary is None:
        return {}
    return {
        "recommendation": summary.recommendation,
        "section": summary.section,
        "level": summary.level,
        "result": summary.compliant,
        "findings": summary.findings,
        "compliantItems": summary.compliant_items,
        "total": summary.total,
        "compliancePercentage": summary.compliance_percentage,
        "title": summary.title,
        "cisV8": summary.cis_v8,
        "cccsGuardRail": summary.cccs_guard_rail,
        "regions": summary.regions,
        "remediation": summary.remediation,
        "extractDate": summary.extract_date,
    }


def _stable_finding_id(
    *,
    tenancy_id: str,
    benchmark_version: str,
    control_display_id: str,
    scope_type: str,
    scope_key: str,
    region: str | None,
) -> str:
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


def _first_present(payload: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = _blank_to_none(payload.get(key))
        if value:
            return value
    return None


def _first_region(summary: SummaryRow | None) -> str | None:
    if summary and summary.regions:
        return summary.regions[0]
    return None


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _blank_to_none(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _coerce_datetime(value: str | None) -> str | None:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    if cleaned.endswith("Z"):
        return cleaned
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}t\d{2}:\d{2}:\d{2}", cleaned.lower()):
        return cleaned + "Z"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}( utc)?", cleaned.lower()):
        return cleaned[:19].replace(" ", "T") + "Z"
    return cleaned


def _relative_or_none(path: Path | None, root: Path) -> str | None:
    return path.relative_to(root).as_posix() if path else None


def _write_logs(layout: RunLayout, logs: list[dict[str, Any]]) -> Path:
    log_path = layout.logs_dir / "events.jsonl"
    log_path.write_text(
        "".join(json.dumps(event, sort_keys=True) + "\n" for event in logs),
        encoding="utf-8",
    )
    return log_path


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
