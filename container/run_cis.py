"""Run Oracle CIS reports and publish the app-compatible Object Storage layout."""

from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import oci
from cis_reports import CIS_Report

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required container environment variable: {name}")
    return value


def as_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def object_key(run_id: str, *parts: str) -> str:
    prefix = os.environ.get("OBJECT_PREFIX", "").strip("/")
    suffix = "/".join(part.strip("/") for part in parts if part)
    return "/".join(part for part in (prefix, run_id, suffix) if part)


def put_json(client: Any, namespace: str, bucket: str, name: str, payload: dict[str, Any]) -> None:
    client.put_object(
        namespace,
        bucket,
        name,
        json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"),
        content_type="application/json",
        opc_meta={"run-id": payload.get("runId", "")},
    )


def upload_report_files(client: Any, namespace: str, bucket: str, run_id: str, report_dir: Path) -> int:
    count = 0
    for path in sorted(report_dir.rglob("*")):
        if not path.is_file():
            continue
        relative_name = path.relative_to(report_dir).as_posix()
        target = object_key(run_id, "files", relative_name)
        with path.open("rb") as handle:
            client.put_object(
                namespace,
                bucket,
                target,
                handle,
                opc_meta={"run-id": run_id, "report-file": relative_name},
            )
        count += 1
    return count


def resolve_regions(config: dict[str, Any], signer: Any, requested: str) -> str:
    cleaned = requested.strip()
    if cleaned.lower() != "all":
        return cleaned

    identity_client = oci.identity.IdentityClient(config, signer=signer)
    subscriptions = identity_client.list_region_subscriptions(config["tenancy"]).data
    regions = [
        subscription.region_name
        for subscription in subscriptions
        if getattr(subscription, "status", "READY") == "READY"
    ]
    if not regions:
        raise RuntimeError("No READY OCI region subscriptions found for CIS_REGIONS=All")
    return ",".join(sorted(set(regions)))


def upload_failure(client: Any, namespace: str, bucket: str, run_id: str, stage: str, error: Exception) -> None:
    put_json(
        client,
        namespace,
        bucket,
        object_key(run_id, "_FAILED"),
        {
            "runId": run_id,
            "status": "FAILED",
            "stage": stage,
            "errorType": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
            "completedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        },
    )


def main() -> None:
    run_id = required("RUN_ID")
    output_bucket = required("OUTPUT_BUCKET")
    report_directory = Path("/tmp") / run_id / "reports"
    report_directory.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    signer = oci.auth.signers.get_resource_principals_signer()
    config = {
        "region": signer.region,
        "tenancy": signer.tenancy_id,
        "retry_strategy": oci.retry.DEFAULT_RETRY_STRATEGY,
    }
    object_client = oci.object_storage.ObjectStorageClient(config, signer=signer)
    namespace = object_client.get_namespace().data
    stage = "initializing CIS_Report"

    try:
        requested_regions = resolve_regions(config, signer, os.environ.get("CIS_REGIONS", "All"))
        report = CIS_Report(
            config=config,
            signer=signer,
            proxy=None,
            output_bucket=None,
            report_directory=str(report_directory),
            report_prefix=None,
            report_summary_json=True,
            print_to_screen="False",
            regions_to_run_in=requested_regions,
            raw_data=as_bool("CIS_INCLUDE_RAW"),
            obp=as_bool("CIS_INCLUDE_OBP"),
            redact_output=as_bool("CIS_REDACT_OUTPUT"),
            oci_url=None,
            debug=as_bool("CIS_DEBUG"),
            all_resources=as_bool("CIS_ALL_RESOURCES"),
        )
        stage = "generating CIS reports"
        report.generate_reports(int(os.environ.get("CIS_LEVEL", "2")))

        summary_file = report_directory / "cis_summary_report.json"
        if not summary_file.is_file():
            raise RuntimeError("CIS run did not produce cis_summary_report.json")

        stage = "uploading report files"
        file_count = upload_report_files(object_client, namespace, output_bucket, run_id, report_directory)
        completed_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        ready = {
            "runId": run_id,
            "status": "SUCCESS",
            "bucket": output_bucket,
            "namespace": namespace,
            "filesPrefix": object_key(run_id, "files"),
            "reportFileCount": file_count,
            "scannerVersion": "3.3.0",
            "requestedRegions": requested_regions,
            "benchmarkLevel": os.environ.get("CIS_LEVEL", "2"),
            "startedAt": started_at,
            "completedAt": completed_at,
        }
        put_json(object_client, namespace, output_bucket, object_key(run_id, "run_ready.json"), ready)
        object_client.put_object(
            namespace,
            output_bucket,
            object_key(run_id, "_SUCCESS"),
            (completed_at + "\n").encode("utf-8"),
            content_type="text/plain",
            opc_meta={"run-id": run_id, "report-status": "SUCCESS"},
        )
    except Exception as error:
        try:
            upload_failure(object_client, namespace, output_bucket, run_id, stage, error)
        except Exception:
            LOG.exception("Unable to upload CIS failure diagnostic")
        LOG.exception("CIS runner failed during %s", stage)
        raise

    LOG.info(json.dumps({"status": "uploaded", "bucket": output_bucket, "runId": run_id}))


if __name__ == "__main__":
    main()
