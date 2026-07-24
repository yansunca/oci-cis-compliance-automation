"""Ingest a completed CIS package into Autonomous Database Serverless.

The Function receives Object Storage create events, extracts the CIS summary,
writes one newline-delimited JSON staging object, and invokes an ADB procedure
that uses DBMS_CLOUD.COPY_DATA.  ADB, rather than the Function, performs the
bulk load from Object Storage using its resource principal.
"""

import base64
import io
import json
import logging
import os
import re
import shutil
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from urllib.parse import quote

import oci
import oracledb
from fdk import response


LOG = logging.getLogger()
LOG.setLevel(logging.INFO)

MAX_SUMMARY_BYTES = 10 * 1024 * 1024
RUN_ID_RE = re.compile(r"^cis-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{10}$")
COPY_DATA_RETRY_DELAYS_SECONDS = (5, 10, 20)


def required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required Function configuration: {name}")
    return value


def text(value) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def integer(value) -> int | None:
    value = text(value)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def event_object(data: io.BytesIO) -> tuple[str, str] | None:
    """Return the bucket/object pair only for canonical CIS report packages."""
    body = json.loads((data.getvalue() if data else b"{}").decode("utf-8"))
    event_data = body.get("data", {})
    details = event_data.get("additionalDetails", {})
    bucket = details.get("bucketName")
    # OCI Object Storage create events identify the object key as resourceName.
    # Keep the additionalDetails fallback for direct invocations and compatible
    # producers that provide objectName there.
    object_name = event_data.get("resourceName") or details.get("objectName")
    if bucket != required("REPORT_BUCKET") or not isinstance(object_name, str):
        return None

    parts = object_name.split("/")
    if len(parts) != 3 or parts[0] != "runs" or parts[2] != "cis-report.zip":
        # This safely ignores the Function's own staged-object create event.
        return None
    if not RUN_ID_RE.fullmatch(parts[1]):
        raise ValueError(f"Unexpected CIS report run ID: {parts[1]!r}")
    return bucket, object_name


def load_secret_bytes(signer, config: dict, secret_id: str) -> bytes:
    client = oci.secrets.SecretsClient(config, signer=signer)
    bundle = client.get_secret_bundle(secret_id).data
    encoded = bundle.secret_bundle_content.content
    return base64.b64decode(encoded)


def load_secret(signer, config: dict, secret_id: str) -> str:
    return load_secret_bytes(signer, config, secret_id).decode("utf-8")


def unpack_wallet(signer, config: dict) -> str:
    chunk_ids = required("ADB_WALLET_CHUNK_SECRET_IDS").split(",")
    wallet_base64 = "".join(
        chunk
        for secret_id in chunk_ids
        if (chunk := load_secret(signer, config, secret_id)) != "."
    )
    wallet = base64.b64decode(wallet_base64)
    wallet_dir = tempfile.mkdtemp(prefix="adb-wallet-", dir="/tmp")
    with zipfile.ZipFile(io.BytesIO(wallet)) as archive:
        archive.extractall(wallet_dir)
    return wallet_dir


def extract_summary(package: bytes) -> list[dict]:
    if not zipfile.is_zipfile(io.BytesIO(package)):
        raise ValueError("The Object Storage report is not a ZIP archive")

    with zipfile.ZipFile(io.BytesIO(package)) as archive:
        try:
            info = archive.getinfo("cis_summary_report.json")
        except KeyError as error:
            raise ValueError("cis_summary_report.json is missing from the CIS archive") from error
        if info.file_size > MAX_SUMMARY_BYTES:
            raise ValueError("cis_summary_report.json exceeds the 10 MiB ingestion limit")
        summary = json.loads(archive.read(info).decode("utf-8"))

    if not isinstance(summary, list) or not all(isinstance(item, dict) for item in summary):
        raise ValueError("cis_summary_report.json must contain an array of JSON objects")
    return summary


def normalize(summary: list[dict], run_id: str, source_object: str) -> bytes:
    ingested_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    records = []
    for recommendation in summary:
        records.append(
            {
                "run_id": run_id,
                "source_object": source_object,
                "ingested_at": ingested_at,
                "recommendation_number": text(recommendation.get("Recommendation #")),
                "section_name": text(recommendation.get("Section")),
                "benchmark_level": integer(recommendation.get("Level")),
                "is_compliant": text(recommendation.get("Compliant")),
                "findings": text(recommendation.get("Findings")),
                "compliant_items": integer(recommendation.get("Compliant Items")),
                "total_items": integer(recommendation.get("Total")),
                "compliance_percentage": text(
                    recommendation.get("Compliance Percentage Per Recommendation")
                ),
                "title": text(recommendation.get("Title")),
                "cis_v8_json": json.dumps(recommendation.get("CIS v8", []), separators=(",", ":")),
                "cccs_guard_rail_json": json.dumps(
                    recommendation.get("CCCS Guard Rail", []), separators=(",", ":")
                ),
                "regions_json": json.dumps(recommendation.get("Regions", []), separators=(",", ":")),
                "source_filename": text(recommendation.get("Filename")),
                "remediation": text(recommendation.get("Remediation")),
                "raw_record": json.dumps(recommendation, separators=(",", ":"), sort_keys=True),
            }
        )

    if not records:
        raise ValueError("cis_summary_report.json did not contain any recommendations")
    return ("\n".join(json.dumps(record, separators=(",", ":")) for record in records) + "\n").encode(
        "utf-8"
    )


def ensure_database(cursor) -> None:
    cursor.execute(
        """
        DECLARE
          credential_count PLS_INTEGER;
        BEGIN
          SELECT COUNT(*) INTO credential_count
          FROM dba_credentials
          WHERE owner = 'ADMIN' AND credential_name = 'OCI$RESOURCE_PRINCIPAL';
          IF credential_count = 0 THEN
            DBMS_CLOUD_ADMIN.ENABLE_RESOURCE_PRINCIPAL();
          END IF;
        END;
        """
    )
    cursor.execute(
        """
        DECLARE
          already_exists EXCEPTION;
          PRAGMA EXCEPTION_INIT(already_exists, -955);
        BEGIN
          EXECUTE IMMEDIATE q'~
            CREATE TABLE CIS_RESULTS (
              RUN_ID VARCHAR2(64) NOT NULL,
              SOURCE_OBJECT VARCHAR2(1024) NOT NULL,
              INGESTED_AT TIMESTAMP WITH TIME ZONE NOT NULL,
              RECOMMENDATION_NUMBER VARCHAR2(32) NOT NULL,
              SECTION_NAME VARCHAR2(256),
              BENCHMARK_LEVEL NUMBER(2),
              IS_COMPLIANT VARCHAR2(3),
              FINDINGS CLOB,
              COMPLIANT_ITEMS NUMBER,
              TOTAL_ITEMS NUMBER,
              COMPLIANCE_PERCENTAGE VARCHAR2(16),
              TITLE VARCHAR2(1000),
              CIS_V8_JSON CLOB CHECK (CIS_V8_JSON IS JSON),
              CCCS_GUARD_RAIL_JSON CLOB CHECK (CCCS_GUARD_RAIL_JSON IS JSON),
              REGIONS_JSON CLOB CHECK (REGIONS_JSON IS JSON),
              SOURCE_FILENAME VARCHAR2(1024),
              REMEDIATION CLOB,
              RAW_RECORD CLOB CHECK (RAW_RECORD IS JSON),
              CONSTRAINT CIS_RESULTS_PK PRIMARY KEY (RUN_ID, RECOMMENDATION_NUMBER)
            )
          ~';
        EXCEPTION
          WHEN already_exists THEN NULL;
        END;
        """
    )
    cursor.execute(
        """
        CREATE OR REPLACE PROCEDURE CIS_LOAD_REPORT (
          p_run_id IN VARCHAR2,
          p_object_uri IN VARCHAR2
        ) AUTHID DEFINER AS
        BEGIN
          DELETE FROM CIS_RESULTS WHERE RUN_ID = p_run_id;
          -- COPY_DATA uses a separate loader session. Commit the replacement
          -- delete first so that session is not blocked by the row locks.
          COMMIT;
          DBMS_CLOUD.COPY_DATA(
            table_name      => 'CIS_RESULTS',
            credential_name => 'OCI$RESOURCE_PRINCIPAL',
            file_uri_list   => p_object_uri,
            format          => JSON_OBJECT(
              'type' VALUE 'json',
              'recorddelimiter' VALUE 'newline',
              'columnpath' VALUE '["$.run_id","$.source_object","$.ingested_at","$.recommendation_number","$.section_name","$.benchmark_level","$.is_compliant","$.findings","$.compliant_items","$.total_items","$.compliance_percentage","$.title","$.cis_v8_json","$.cccs_guard_rail_json","$.regions_json","$.source_filename","$.remediation","$.raw_record"]'
            )
          );
        END;
        """
    )


def load_report(connection, cursor, run_id: str, staged_uri: str) -> None:
    """Retry transient COPY_DATA deadlocks caused by duplicate event deliveries."""
    for attempt in range(len(COPY_DATA_RETRY_DELAYS_SECONDS) + 1):
        try:
            cursor.callproc("CIS_LOAD_REPORT", [run_id, staged_uri])
            return
        except oracledb.DatabaseError as error:
            if "ORA-00060" not in str(error) or attempt == len(COPY_DATA_RETRY_DELAYS_SECONDS):
                raise
            connection.rollback()
            delay = COPY_DATA_RETRY_DELAYS_SECONDS[attempt]
            LOG.warning(
                "DBMS_CLOUD.COPY_DATA deadlocked for run %s; retrying in %s seconds",
                run_id,
                delay,
            )
            time.sleep(delay)


def handler(ctx, data: io.BytesIO = None):
    try:
        event = event_object(data)
        if event is None:
            return response.Response(ctx, response_data='{"status":"ignored"}', status_code=204)
        bucket, source_object = event
        run_id = source_object.split("/")[1]

        signer = oci.auth.signers.get_resource_principals_signer()
        config = {"region": signer.region, "tenancy": signer.tenancy_id}
        object_client = oci.object_storage.ObjectStorageClient(config, signer=signer)
        namespace = object_client.get_namespace().data
        package = object_client.get_object(namespace, bucket, source_object).data.content
        summary = extract_summary(package)

        staged_name = f"staged/{run_id}/cis_results.ndjson"
        payload = normalize(summary, run_id, source_object)
        object_client.put_object(
            namespace,
            bucket,
            staged_name,
            payload,
            content_type="application/x-ndjson",
            opc_meta={"run-id": run_id, "source-object": source_object},
        )

        staged_uri = (
            f"https://objectstorage.{signer.region}.oraclecloud.com/n/{namespace}/b/{bucket}/o/"
            f"{quote(staged_name, safe='/')}"
        )
        password = load_secret(signer, config, required("ADB_ADMIN_PASSWORD_SECRET_ID"))
        wallet_password = load_secret(
            signer, config, required("ADB_WALLET_PASSWORD_SECRET_ID")
        )
        wallet_dir = unpack_wallet(signer, config)
        try:
            with oracledb.connect(
                user="ADMIN",
                password=password,
                dsn=required("ADB_TNS_ALIAS"),
                config_dir=wallet_dir,
                wallet_location=wallet_dir,
                wallet_password=wallet_password,
            ) as connection:
                with connection.cursor() as cursor:
                    ensure_database(cursor)
                    load_report(connection, cursor, run_id, staged_uri)
                connection.commit()
        finally:
            shutil.rmtree(wallet_dir, ignore_errors=True)

        message = {
            "status": "loaded",
            "run_id": run_id,
            "source_object": source_object,
            "staged_object": staged_name,
            "recommendation_count": len(summary),
        }
        LOG.info(json.dumps(message))
        return response.Response(ctx, response_data=json.dumps(message), status_code=202)
    except Exception as error:
        LOG.exception("CIS report ingestion failed")
        message = {"status": "error", "error_type": type(error).__name__, "message": str(error)}
        return response.Response(ctx, response_data=json.dumps(message), status_code=500)
