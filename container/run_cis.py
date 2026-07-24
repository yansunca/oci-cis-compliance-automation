"""Run Oracle's CIS report class with a Container Instance resource principal.

This is intentionally the same CIS_Report construction used by the referenced
OCI Functions blog. It packages the locally generated reports into one object
instead of passing output_bucket to CIS_Report, which would emit one event per
CSV/JSON file and make downstream processing non-deterministic.
"""

import json
import logging
import os
import traceback
import zipfile
from pathlib import Path

import oci
from cis_reports import CIS_Report


LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required container environment variable: {name}")
    return value


def as_bool(name: str) -> bool:
    return os.environ.get(name, "false").lower() in {"1", "true", "yes", "on"}


def create_archive(directory: Path, archive_path: Path) -> None:
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(directory))


def upload_json_diagnostic(
    object_client: oci.object_storage.ObjectStorageClient,
    namespace: str,
    output_bucket: str,
    run_id: str,
    name: str,
    payload: dict,
) -> None:
    """Persist a small, non-secret diagnostic for a one-shot container failure."""
    object_client.put_object(
        namespace,
        output_bucket,
        f"runs/{run_id}/{name}",
        json.dumps(payload, sort_keys=True).encode("utf-8"),
        content_type="application/json",
        opc_meta={"run-id": run_id, "report-format": "oci-cis-diagnostic-v1"},
    )


def main() -> None:
    run_id = required("RUN_ID")
    output_bucket = required("OUTPUT_BUCKET")
    report_directory = Path("/tmp") / run_id
    archive_path = Path("/tmp") / "cis-report.zip"

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
        # This mirrors the blog's Function handler, replacing its /tmp output with a
        # run-specific directory. output_bucket remains None until the zip is complete.
        report = CIS_Report(
            config=config,
            signer=signer,
            proxy=None,
            output_bucket=None,
            report_directory=str(report_directory),
            report_prefix=None,
            report_summary_json=True,
            # CIS_Report 3.3.0 normalizes this setting with .upper(), so it
            # must remain a string even though the other feature flags are booleans.
            print_to_screen="False",
            regions_to_run_in=os.environ.get("CIS_REGIONS", "All"),
            raw_data=as_bool("CIS_INCLUDE_RAW"),
            obp=as_bool("CIS_INCLUDE_OBP"),
            redact_output=as_bool("CIS_REDACT_OUTPUT"),
            oci_url=None,
            debug=False,
            all_resources=False,
        )
        stage = "generating CIS reports"
        report.generate_reports(int(os.environ.get("CIS_LEVEL", "2")))

        summary_file = report_directory / "cis_summary_report.json"
        if not summary_file.is_file():
            raise RuntimeError("CIS run did not produce cis_summary_report.json")

        stage = "creating report archive"
        create_archive(report_directory, archive_path)
        object_name = f"runs/{run_id}/cis-report.zip"
        stage = "uploading report archive"
        with archive_path.open("rb") as package:
            object_client.put_object(
                namespace,
                output_bucket,
                object_name,
                package,
                content_type="application/zip",
                opc_meta={"run-id": run_id, "report-format": "oci-cis-summary-v1"},
            )
    except Exception as error:
        diagnostic = {
            "error_message": str(error),
            "error_type": type(error).__name__,
            "run_id": run_id,
            "stage": stage,
            "traceback": traceback.format_exc(),
        }
        try:
            upload_json_diagnostic(
                object_client, namespace, output_bucket, run_id, "failure.json", diagnostic
            )
        except Exception:
            LOG.exception("Unable to upload CIS failure diagnostic")
        LOG.exception("CIS runner failed during %s", stage)
        raise

    LOG.info(json.dumps({"status": "uploaded", "bucket": output_bucket, "object": object_name}))


if __name__ == "__main__":
    main()
