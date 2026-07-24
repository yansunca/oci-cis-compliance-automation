"""Command-line entrypoints for native OCI CIS report conversion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from scanner.native_report_converter import convert_native_report_run

ROOT = Path(__file__).resolve().parents[1]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m scanner.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    native_report_run = subparsers.add_parser(
        "native-report-run",
        help="Convert a native OCI CIS report folder into wrapper output artifacts.",
    )
    native_report_run.add_argument("--native-report-dir", required=True, type=Path)
    native_report_run.add_argument("--output-root", required=True, type=Path)
    native_report_run.add_argument("--run-id", required=True)
    native_report_run.add_argument("--tenancy-id", required=True)
    native_report_run.add_argument("--started-at")
    native_report_run.add_argument("--completed-at")
    native_report_run.add_argument("--scanner-version", default="UNKNOWN")
    native_report_run.add_argument("--scanner-commit", default="UNKNOWN")
    native_report_run.add_argument("--scanner-source-checksum")
    native_report_run.add_argument("--scanner-image-digest", default="UNKNOWN")
    native_report_run.add_argument("--benchmark-version")
    native_report_run.add_argument("--benchmark-level", default="2")
    native_report_run.add_argument("--requested-region", action="append", dest="requested_regions")
    native_report_run.add_argument("--completed-region", action="append", dest="completed_regions")
    native_report_run.add_argument("--source-object-uri-prefix")

    args = parser.parse_args(argv)
    if args.command == "native-report-run":
        result = convert_native_report_run(
            native_report_dir=args.native_report_dir,
            output_root=args.output_root,
            run_id=args.run_id,
            tenancy_id=args.tenancy_id,
            started_at=args.started_at,
            completed_at=args.completed_at,
            scanner_version=args.scanner_version,
            scanner_commit=args.scanner_commit,
            scanner_source_checksum=args.scanner_source_checksum,
            scanner_image_digest=args.scanner_image_digest,
            benchmark_version=args.benchmark_version,
            benchmark_level=args.benchmark_level,
            requested_regions=args.requested_regions,
            completed_regions=args.completed_regions,
            source_object_uri_prefix=args.source_object_uri_prefix,
        )
        print(
            json.dumps(
                {
                    "status": result.status,
                    "runId": args.run_id,
                    "runDir": result.layout.run_dir.as_posix(),
                    "landingRecordCount": result.landing_record_count,
                    "canonicalFindingCount": result.canonical_finding_count,
                    "nativeErrorCount": result.native_error_count,
                    "errorMessage": result.error_message,
                },
                sort_keys=True,
            ),
        )
        return 0 if result.status == "SUCCESS" else 1
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
