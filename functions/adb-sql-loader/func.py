"""ADB SQL loader Function for completed OCI CIS report runs.

This Function is invoked by the Object Storage completion-marker handler after
both `<run_id>/run_ready.json` and `<run_id>/_SUCCESS` exist. It downloads the
native upstream CIS report bundle, converts it into the app's canonical staging
layout, generates the same SQLcl load scripts used by the manual demo path, and
loads the run into Autonomous Database.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import logging
import os
import re
import shutil
import sys
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

try:  # pragma: no cover - exercised in OCI Functions runtime
    import oci
    from fdk import response
except ImportError:  # pragma: no cover - keeps local unit tests dependency-free
    oci = None  # type: ignore[assignment]
    response = None  # type: ignore[assignment]


FUNCTION_ROOT = Path(__file__).resolve().parent
path_parents = Path(__file__).resolve().parents
repo_candidates = [FUNCTION_ROOT]
if len(path_parents) > 2:
    repo_candidates.append(path_parents[2])
for candidate in repo_candidates:
    if (candidate / "scanner").is_dir() and candidate.as_posix() not in sys.path:
        sys.path.insert(0, candidate.as_posix())

from scanner.native_report_converter import convert_native_report_run  # noqa: E402
from scripts.build_adb_direct_load_sql import build_sql as build_adb_load_sql  # noqa: E402
from scripts.build_evidence_artifact_cache_load_sql import (  # noqa: E402
    build_sql as build_evidence_load_sql,
)


RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
DEFAULT_WORK_ROOT = Path("/tmp/oci-cis-adb-sql-loader")
DEFAULT_CONNECT_ALIAS = "cisfindatp_low"

logging.basicConfig(level=logging.INFO)
logging.getLogger("oci").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


def configure_csv_field_limit() -> int:
    limit = sys.maxsize
    while limit > 131072:
        try:
            csv.field_size_limit(limit)
            return limit
        except OverflowError:
            limit //= 10
    csv.field_size_limit(131072)
    return 131072


CSV_FIELD_SIZE_LIMIT = configure_csv_field_limit()


@dataclass(frozen=True)
class LoadRequest:
    run_id: str
    bucket: str
    namespace: str | None
    source_prefix: str
    run_ready_object: str
    tenancy_id: str
    scanner_version: str
    scanner_commit: str
    benchmark_version: str
    benchmark_level: str
    requested_regions: list[str]
    completed_regions: list[str]
    started_at: str | None
    completed_at: str | None
    source_object_uri_prefix: str
    reconcile_absent: bool


@dataclass(frozen=True)
class LoadPaths:
    work_root: Path
    native_report_dir: Path
    converted_root: Path
    converted_run_dir: Path
    adb_sql_file: Path
    evidence_sql_file: Path
    wallet_dir: Path
    password_file: Path


def handler(ctx: object, data: io.BytesIO | None = None) -> object:
    status_code = 200
    try:
        payload = _load_payload(data)
        mode = str(payload.get("mode", "")).lower()
        if mode == "health":
            result = health(env=os.environ, ctx=ctx)
        elif mode == "verifyrun":
            result = verify_run(payload, ctx=ctx)
        elif mode == "executesqlobjects":
            result = execute_sql_objects(payload, ctx=ctx)
        elif mode == "verifyreadonlycleanup":
            result = verify_readonly_cleanup(payload, ctx=ctx)
        else:
            result = load_completed_run(payload, ctx=ctx)
    except Exception as exc:  # noqa: BLE001 - Function response must be explicit for logs.
        status_code = 500
        result = {
            "status": "failed",
            "errorType": type(exc).__name__,
            "message": str(exc),
        }
        _emit_log("adb_sql_loader_failed", **result)

    if response is None:
        return result

    return response.Response(
        ctx,
        response_data=json.dumps(result, indent=2, sort_keys=True),
        status_code=status_code,
        headers={"Content-Type": "application/json"},
    )


def health(*, env: Mapping[str, str] | None = None, ctx: object | None = None) -> dict[str, Any]:
    env = env or os.environ
    cfg = _ctx_config(ctx)
    return {
        "status": "ok",
        "component": "adb-sql-loader-function",
        "sqlExecutor": _first(cfg.get("OCI_CIS_SQL_EXECUTOR"), env.get("OCI_CIS_SQL_EXECUTOR"), "oracledb"),
        "hasBucket": bool(_first(cfg.get("OCI_CIS_OBJECT_BUCKET"), env.get("OCI_CIS_OBJECT_BUCKET"))),
        "hasTenancyId": bool(_first(cfg.get("OCI_CIS_TENANCY_ID"), env.get("OCI_CIS_TENANCY_ID"))),
        "hasWalletObject": bool(_first(cfg.get("OCI_CIS_ADB_WALLET_OBJECT"), env.get("OCI_CIS_ADB_WALLET_OBJECT"))),
        "hasWalletChunkSecrets": bool(
            _first(
                cfg.get("OCI_CIS_ADB_WALLET_CHUNK_SECRET_OCIDS"),
                env.get("OCI_CIS_ADB_WALLET_CHUNK_SECRET_OCIDS"),
            ),
        ),
        "hasPasswordSecret": bool(
            _first(
                cfg.get("OCI_CIS_ADB_PASSWORD_SECRET_OCID"),
                env.get("OCI_CIS_ADB_PASSWORD_SECRET_OCID"),
            ),
        ),
        "hasWalletPasswordSecret": bool(
            _first(
                cfg.get("OCI_CIS_ADB_WALLET_PASSWORD_SECRET_OCID"),
                env.get("OCI_CIS_ADB_WALLET_PASSWORD_SECRET_OCID"),
            ),
        ),
    }


def verify_run(
    payload: Mapping[str, Any],
    *,
    ctx: object | None = None,
    env: Mapping[str, str] | None = None,
    object_client: object | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    run_id = _validated_run_id(payload.get("runId"))
    bucket = _required(_first(payload.get("bucket"), env.get("OCI_CIS_OBJECT_BUCKET")), "bucket")
    request = build_load_request(
        {
            "runId": run_id,
            "bucket": bucket,
            "namespace": payload.get("namespace"),
            "sourcePrefix": f"{run_id}/files/",
        },
        env=env,
        ctx=ctx,
    )
    paths = build_load_paths(f"{run_id}-verify", env=env)
    if paths.work_root.exists():
        shutil.rmtree(paths.work_root)
    paths.work_root.mkdir(parents=True, exist_ok=True)

    client = object_client or _object_storage_client()
    prepare_adb_credentials(client, request, paths, env=env)
    result = query_run_counts_with_oracledb(run_id, paths, env)
    _emit_log("adb_sql_loader_verify_run", **result)
    return result


def load_completed_run(
    payload: Mapping[str, Any],
    *,
    ctx: object | None = None,
    env: Mapping[str, str] | None = None,
    object_client: object | None = None,
    sqlcl_runner: Any | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    request = build_load_request(payload, env=env, ctx=ctx)
    paths = build_load_paths(request.run_id, env=env)

    _emit_log(
        "adb_sql_loader_start",
        run_id=request.run_id,
        bucket=request.bucket,
        source_prefix=request.source_prefix,
    )

    if paths.work_root.exists():
        shutil.rmtree(paths.work_root)
    paths.native_report_dir.mkdir(parents=True, exist_ok=True)
    paths.converted_root.mkdir(parents=True, exist_ok=True)

    client = object_client or _object_storage_client()
    downloaded = download_report_bundle(client, request, paths.native_report_dir)
    _emit_log(
        "adb_sql_loader_reports_downloaded",
        run_id=request.run_id,
        downloaded_report_file_count=downloaded,
    )

    conversion = convert_native_report_run(
        native_report_dir=paths.native_report_dir,
        output_root=paths.converted_root,
        run_id=request.run_id,
        tenancy_id=request.tenancy_id,
        started_at=request.started_at,
        completed_at=request.completed_at,
        scanner_version=request.scanner_version,
        scanner_commit=request.scanner_commit,
        benchmark_version=request.benchmark_version,
        benchmark_level=request.benchmark_level,
        requested_regions=request.requested_regions,
        completed_regions=request.completed_regions,
        source_object_uri_prefix=request.source_object_uri_prefix,
    )
    if conversion.status != "SUCCESS":
        raise RuntimeError(conversion.error_message or "native report conversion failed")
    _emit_log(
        "adb_sql_loader_reports_converted",
        run_id=request.run_id,
        canonical_finding_count=conversion.canonical_finding_count,
        landing_record_count=conversion.landing_record_count,
        native_error_count=conversion.native_error_count,
    )

    paths.adb_sql_file.parent.mkdir(parents=True, exist_ok=True)
    paths.adb_sql_file.write_text(
        build_adb_load_sql(paths.converted_run_dir, reconcile_absent=request.reconcile_absent),
        encoding="utf-8",
    )
    paths.evidence_sql_file.write_text(
        build_evidence_load_sql(
            paths.converted_run_dir / "reports",
            run_id=request.run_id,
            source_prefix=f"oci://{request.bucket}/{request.source_prefix.rstrip('/')}",
        ),
        encoding="utf-8",
    )
    _emit_log(
        "adb_sql_loader_sql_generated",
        run_id=request.run_id,
        adb_sql_file=paths.adb_sql_file.name,
        evidence_sql_file=paths.evidence_sql_file.name,
    )

    prepare_adb_credentials(client, request, paths, env=env)
    _emit_log(
        "adb_sql_loader_credentials_ready",
        run_id=request.run_id,
        wallet_file_count=len([item for item in paths.wallet_dir.iterdir() if item.is_file()]),
    )
    sql_runner = sqlcl_runner or run_sql_file
    adb_load = sql_runner(paths.adb_sql_file, paths, env)
    evidence_load = sql_runner(paths.evidence_sql_file, paths, env)
    status = "loaded" if adb_load["exitCode"] == 0 and evidence_load["exitCode"] == 0 else "failed"

    result = {
        "status": status,
        "runId": request.run_id,
        "downloadedReportFileCount": downloaded,
        "canonicalFindingCount": conversion.canonical_finding_count,
        "landingRecordCount": conversion.landing_record_count,
        "nativeErrorCount": conversion.native_error_count,
        "adbLoadExitCode": adb_load["exitCode"],
        "evidenceLoadExitCode": evidence_load["exitCode"],
        "convertedRunDir": paths.converted_run_dir.as_posix(),
    }
    _emit_log("adb_sql_loader_complete", **result)
    if status != "loaded":
        raise RuntimeError("SQLcl load failed; see Function logs for redacted SQLcl output")
    return result


def execute_sql_objects(
    payload: Mapping[str, Any],
    *,
    ctx: object | None = None,
    env: Mapping[str, str] | None = None,
    object_client: object | None = None,
    sqlcl_runner: Any | None = None,
) -> dict[str, Any]:
    """Execute reviewed SQL files stored in Object Storage.

    This is an operational escape hatch for DBA-approved maintenance SQL. It is
    intentionally object-based so the Function payload does not carry SQL text.
    """

    env = env or os.environ
    cfg = _ctx_config(ctx)
    bucket = _required(
        _first(payload.get("bucket"), payload.get("bucketName"), cfg.get("bucket"), env.get("OCI_CIS_OBJECT_BUCKET")),
        "bucket",
    )
    namespace = _optional_string(_first(payload.get("namespace"), cfg.get("namespace")))
    object_names = _validated_sql_object_names(payload.get("sqlObjects"))
    run_id = _validated_run_id(
        _first(
            payload.get("operationId"),
            cfg.get("operation_id"),
            "ADMIN-SQL-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        ),
    )
    tenancy_id = _required(
        _first(payload.get("tenancyId"), cfg.get("tenancy_id"), env.get("OCI_CIS_TENANCY_ID")),
        "tenancyId",
    )
    request = LoadRequest(
        run_id=run_id,
        bucket=bucket,
        namespace=namespace,
        source_prefix="",
        run_ready_object="",
        tenancy_id=tenancy_id,
        scanner_version="ADMIN_SQL",
        scanner_commit="N/A",
        benchmark_version="N/A",
        benchmark_level="N/A",
        requested_regions=[],
        completed_regions=[],
        started_at=None,
        completed_at=None,
        source_object_uri_prefix=f"oci://{bucket}",
        reconcile_absent=False,
    )
    paths = build_load_paths(run_id, env=env)
    if paths.work_root.exists():
        shutil.rmtree(paths.work_root)
    paths.work_root.mkdir(parents=True, exist_ok=True)
    paths.adb_sql_file.parent.mkdir(parents=True, exist_ok=True)

    client = object_client or _object_storage_client()
    namespace_value = namespace or _get_namespace(client)
    prepare_adb_credentials(client, request, paths, env=env)

    sql_runner = sqlcl_runner or run_sql_file
    applied: list[dict[str, Any]] = []
    for index, object_name in enumerate(object_names, start=1):
        local_sql = paths.adb_sql_file.parent / f"{index:03d}-{Path(object_name).name}"
        _download_object(client, namespace_value, bucket, object_name, local_sql)
        result = sql_runner(local_sql, paths, env)
        applied.append(
            {
                "objectName": object_name,
                "localFile": local_sql.name,
                "exitCode": result["exitCode"],
                "executedStatementCount": result.get("executedStatementCount"),
            },
        )
        if result["exitCode"] != 0:
            raise RuntimeError(f"SQL object execution failed: {object_name}")

    response_payload = {
        "status": "applied",
        "operationId": run_id,
        "bucket": bucket,
        "appliedSqlObjects": applied,
    }
    _emit_log("adb_sql_loader_execute_sql_objects_complete", **response_payload)
    return response_payload


def verify_readonly_cleanup(
    payload: Mapping[str, Any],
    *,
    ctx: object | None = None,
    env: Mapping[str, str] | None = None,
    object_client: object | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    cfg = _ctx_config(ctx)
    bucket = _required(
        _first(payload.get("bucket"), payload.get("bucketName"), cfg.get("bucket"), env.get("OCI_CIS_OBJECT_BUCKET")),
        "bucket",
    )
    namespace = _optional_string(_first(payload.get("namespace"), cfg.get("namespace")))
    tenancy_id = _required(
        _first(payload.get("tenancyId"), cfg.get("tenancy_id"), env.get("OCI_CIS_TENANCY_ID")),
        "tenancyId",
    )
    run_id = _validated_run_id(
        _first(
            payload.get("operationId"),
            cfg.get("operation_id"),
            "VERIFY-READONLY-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        ),
    )
    request = LoadRequest(
        run_id=run_id,
        bucket=bucket,
        namespace=namespace,
        source_prefix="",
        run_ready_object="",
        tenancy_id=tenancy_id,
        scanner_version="VERIFY",
        scanner_commit="N/A",
        benchmark_version="N/A",
        benchmark_level="N/A",
        requested_regions=[],
        completed_regions=[],
        started_at=None,
        completed_at=None,
        source_object_uri_prefix=f"oci://{bucket}",
        reconcile_absent=False,
    )
    paths = build_load_paths(run_id, env=env)
    if paths.work_root.exists():
        shutil.rmtree(paths.work_root)
    paths.work_root.mkdir(parents=True, exist_ok=True)
    client = object_client or _object_storage_client()
    prepare_adb_credentials(client, request, paths, env=env)

    result = query_readonly_cleanup_status(paths, env)
    _emit_log("adb_sql_loader_verify_readonly_cleanup", **result)
    return result


def build_load_request(
    payload: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    ctx: object | None = None,
) -> LoadRequest:
    env = env or os.environ
    cfg = _ctx_config(ctx)
    run_id = _validated_run_id(_first(payload.get("runId"), cfg.get("run_id")))
    bucket = _required(_first(payload.get("bucket"), payload.get("bucketName"), cfg.get("bucket"), env.get("OCI_CIS_OBJECT_BUCKET")), "bucket")
    source_prefix = _required(_first(payload.get("sourcePrefix"), cfg.get("source_prefix")), "sourcePrefix").strip("/")
    if not source_prefix.endswith("/"):
        source_prefix += "/"

    namespace = _optional_string(_first(payload.get("namespace"), cfg.get("namespace")))
    run_ready_object = _optional_string(_first(payload.get("companionMarker"), cfg.get("run_ready_object")))
    if not run_ready_object or not run_ready_object.endswith("run_ready.json"):
        run_ready_object = f"{run_id}/run_ready.json"

    tenancy_id = _required(_first(payload.get("tenancyId"), cfg.get("tenancy_id"), env.get("OCI_CIS_TENANCY_ID")), "tenancyId")
    requested_regions = _split_regions(_first(payload.get("requestedRegions"), cfg.get("requested_regions"), env.get("OCI_CIS_REQUESTED_REGIONS")))
    completed_regions = _split_regions(_first(payload.get("completedRegions"), cfg.get("completed_regions"), env.get("OCI_CIS_COMPLETED_REGIONS"))) or requested_regions

    return LoadRequest(
        run_id=run_id,
        bucket=bucket,
        namespace=namespace,
        source_prefix=source_prefix,
        run_ready_object=run_ready_object,
        tenancy_id=tenancy_id,
        scanner_version=str(_first(payload.get("scannerVersion"), cfg.get("scanner_version"), env.get("OCI_CIS_SCANNER_VERSION"), "UNKNOWN")),
        scanner_commit=str(_first(payload.get("scannerCommit"), cfg.get("scanner_commit"), env.get("OCI_CIS_SCANNER_COMMIT"), "UNKNOWN")),
        benchmark_version=str(_first(payload.get("benchmarkVersion"), cfg.get("benchmark_version"), env.get("OCI_CIS_BENCHMARK_VERSION"), "UNKNOWN")),
        benchmark_level=str(_first(payload.get("benchmarkLevel"), cfg.get("benchmark_level"), env.get("OCI_CIS_BENCHMARK_LEVEL"), "2")),
        requested_regions=requested_regions or ["UNKNOWN"],
        completed_regions=completed_regions or ["UNKNOWN"],
        started_at=_optional_string(_first(payload.get("startedAt"), cfg.get("started_at"))),
        completed_at=_optional_string(_first(payload.get("completedAt"), cfg.get("completed_at"))),
        source_object_uri_prefix=f"oci://{bucket}/{source_prefix.rstrip('/')}",
        reconcile_absent=_bool_value(_first(payload.get("reconcileAbsent"), cfg.get("reconcile_absent"), env.get("OCI_CIS_RECONCILE_ABSENT")), default=True),
    )


def build_load_paths(run_id: str, *, env: Mapping[str, str] | None = None) -> LoadPaths:
    env = env or os.environ
    work_root = Path(env.get("OCI_CIS_LOADER_WORK_ROOT", DEFAULT_WORK_ROOT.as_posix())) / run_id
    converted_root = work_root / "converted"
    return LoadPaths(
        work_root=work_root,
        native_report_dir=work_root / "native" / run_id / "files",
        converted_root=converted_root,
        converted_run_dir=converted_root / run_id,
        adb_sql_file=work_root / "sql" / f"{run_id}-adb-load.sql",
        evidence_sql_file=work_root / "sql" / f"{run_id}-evidence-load.sql",
        wallet_dir=work_root / "wallet",
        password_file=work_root / "adb-password.txt",
    )


def _validated_sql_object_names(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("sqlObjects must be a non-empty list")
    object_names: list[str] = []
    for item in value:
        if isinstance(item, str):
            object_name = item
        elif isinstance(item, Mapping):
            object_name = str(item.get("objectName", ""))
        else:
            raise ValueError("sqlObjects entries must be strings or objects with objectName")
        object_name = object_name.strip()
        if not object_name or object_name.startswith("/") or ".." in object_name.split("/"):
            raise ValueError(f"unsafe SQL object name: {object_name!r}")
        if not object_name.lower().endswith(".sql"):
            raise ValueError(f"SQL object must end with .sql: {object_name!r}")
        object_names.append(object_name)
    return object_names


def download_report_bundle(client: object, request: LoadRequest, native_report_dir: Path) -> int:
    namespace = request.namespace or _get_namespace(client)
    downloaded = 0
    for object_name in _list_objects(client, namespace, request.bucket, request.source_prefix):
        if object_name.endswith("/"):
            continue
        relative = object_name.removeprefix(request.source_prefix)
        if not relative or "/" in relative:
            continue
        target = native_report_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        _download_object(client, namespace, request.bucket, object_name, target)
        downloaded += 1
    if downloaded == 0:
        raise ValueError(f"no report files found under oci://{request.bucket}/{request.source_prefix}")
    return downloaded


def prepare_adb_credentials(
    client: object,
    request: LoadRequest,
    paths: LoadPaths,
    *,
    env: Mapping[str, str],
) -> None:
    paths.wallet_dir.mkdir(parents=True, exist_ok=True)
    paths.password_file.parent.mkdir(parents=True, exist_ok=True)

    password = _adb_password(env)
    paths.password_file.write_text(password, encoding="utf-8")
    os.chmod(paths.password_file, 0o600)

    wallet_source = env.get("OCI_CIS_ADB_WALLET_DIR", "").strip()
    if wallet_source:
        source_dir = Path(wallet_source)
        if not source_dir.is_dir():
            raise ValueError(f"OCI_CIS_ADB_WALLET_DIR does not exist: {source_dir}")
        for item in source_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, paths.wallet_dir / item.name)
        return

    wallet_zip = paths.work_root / "wallet.zip"
    wallet_chunk_secret_ocids = env.get("OCI_CIS_ADB_WALLET_CHUNK_SECRET_OCIDS", "").strip()
    if wallet_chunk_secret_ocids:
        wallet_base64 = "".join(
            chunk
            for secret_ocid in wallet_chunk_secret_ocids.split(",")
            if (chunk := _read_secret(secret_ocid.strip())) != "."
        )
        wallet_zip.write_bytes(base64.b64decode(wallet_base64))
    else:
        wallet_bucket = env.get("OCI_CIS_ADB_WALLET_BUCKET", request.bucket).strip()
        wallet_object = _required(env.get("OCI_CIS_ADB_WALLET_OBJECT"), "OCI_CIS_ADB_WALLET_OBJECT")
        namespace = request.namespace or _get_namespace(client)
        _download_object(client, namespace, wallet_bucket, wallet_object, wallet_zip)

    with zipfile.ZipFile(wallet_zip) as archive:
        archive.extractall(paths.wallet_dir)


def run_sql_file(sql_file: Path, paths: LoadPaths, env: Mapping[str, str]) -> dict[str, Any]:
    executor = env.get("OCI_CIS_SQL_EXECUTOR", "oracledb").strip().lower()
    if executor == "sqlcl":
        return run_sqlcl_file(sql_file, paths, env)
    return run_sql_file_with_oracledb(sql_file, paths, env)


def run_sql_file_with_oracledb(sql_file: Path, paths: LoadPaths, env: Mapping[str, str]) -> dict[str, Any]:
    connect_alias = env.get("OCI_CIS_ADB_CONNECT_ALIAS", DEFAULT_CONNECT_ALIAS)
    statements = list(_iter_executable_sql(sql_file.read_text(encoding="utf-8")))
    executed_count = 0
    _emit_log(
        "oracledb_sql_file_start",
        sql_file=sql_file.name,
        connect_alias=connect_alias,
        statement_count=len(statements),
    )
    connect_kwargs = _oracledb_connect_kwargs(paths, env)
    import oracledb

    with oracledb.connect(**connect_kwargs) as connection:
        with connection.cursor() as cursor:
            for statement in statements:
                normalized = statement.strip().upper()
                if normalized == "COMMIT":
                    connection.commit()
                    continue
                cursor.execute(statement)
                executed_count += 1
        connection.commit()
    _emit_log("sql_file_complete", sql_file=sql_file.name, executor="oracledb", executed_count=executed_count)
    return {"exitCode": 0, "executedStatementCount": executed_count}


def query_run_counts_with_oracledb(run_id: str, paths: LoadPaths, env: Mapping[str, str]) -> dict[str, Any]:
    import oracledb

    with oracledb.connect(**_oracledb_connect_kwargs(paths, env)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT run_id, status
                FROM scan_run
                WHERE run_id = :run_id
                """,
                run_id=run_id,
            )
            run_row = cursor.fetchone()
            cursor.execute(
                "SELECT COUNT(*) FROM scan_file WHERE run_id = :run_id",
                run_id=run_id,
            )
            file_count = int(cursor.fetchone()[0])
            cursor.execute(
                "SELECT COUNT(*) FROM canonical_finding_stage WHERE run_id = :run_id",
                run_id=run_id,
            )
            stage_count = int(cursor.fetchone()[0])
            cursor.execute(
                "SELECT COUNT(*) FROM finding_observation WHERE run_id = :run_id",
                run_id=run_id,
            )
            observation_count = int(cursor.fetchone()[0])
    return {
        "status": "verified" if run_row else "missing",
        "runId": run_id,
        "scanRun": {
            "runId": run_row[0],
            "status": run_row[1],
            "fileCount": file_count,
        }
        if run_row
        else None,
        "canonicalStageCount": stage_count,
        "observationCount": observation_count,
    }


def query_readonly_cleanup_status(paths: LoadPaths, env: Mapping[str, str]) -> dict[str, Any]:
    import oracledb

    with oracledb.connect(**_oracledb_connect_kwargs(paths, env)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM user_objects
                WHERE object_name IN (
                    'V_CIS_APEX_ACTION_AUDIT',
                    'V_CIS_APEX_FINDING_ACTION_SUMMARY',
                    'FINDING_LIFECYCLE',
                    'APEX_WORKFLOW_SECURITY',
                    'APEX_WORKFLOW_OPERATOR',
                    'FINDING_ACTION_AUDIT',
                    'FINDING_SUPPRESSION',
                    'FINDING_RISK_ACCEPTANCE',
                    'FINDING_COMMENT',
                    'FINDING_ASSIGNMENT'
                )
                """
            )
            retired_object_count = int(cursor.fetchone()[0])
            cursor.execute(
                """
                SELECT object_name, status
                FROM user_objects
                WHERE object_name IN (
                    'V_CIS_APEX_FINDING_DETAIL',
                    'V_CIS_APEX_FINDING_EVIDENCE'
                )
                AND object_type = 'VIEW'
                """
            )
            view_status = {row[0]: row[1] for row in cursor.fetchall()}
            mutable_button_count = _query_optional_count(
                cursor,
                """
                SELECT COUNT(*)
                FROM apex_application_page_buttons
                WHERE application_id = 100
                AND page_id = 20
                AND button_name IN (
                    'ASSIGN_FINDING',
                    'ADD_COMMENT',
                    'ACCEPT_RISK',
                    'SUPPRESS_FINDING'
                )
                """,
            )
            workflow_region_count = _query_optional_count(
                cursor,
                """
                SELECT COUNT(*)
                FROM apex_application_page_regions
                WHERE application_id = 100
                AND page_id = 20
                AND region_name IN ('Workflow Actions', 'Action Audit')
                """,
            )
            cursor.execute("SELECT COUNT(*) FROM v_cis_apex_finding_detail WHERE ROWNUM <= 5")
            sample_detail_rows = int(cursor.fetchone()[0])

    status = "verified"
    if retired_object_count != 0:
        status = "failed"
    if view_status.get("V_CIS_APEX_FINDING_DETAIL") != "VALID":
        status = "failed"
    if view_status.get("V_CIS_APEX_FINDING_EVIDENCE") != "VALID":
        status = "failed"
    if mutable_button_count not in (0, None):
        status = "failed"
    if workflow_region_count not in (0, None):
        status = "failed"

    return {
        "status": status,
        "retiredObjectCount": retired_object_count,
        "viewStatus": view_status,
        "mutableButtonCount": mutable_button_count,
        "workflowRegionCount": workflow_region_count,
        "sampleDetailRows": sample_detail_rows,
    }


def _query_optional_count(cursor: object, sql: str) -> int | None:
    import oracledb

    try:
        cursor.execute(sql)
        return int(cursor.fetchone()[0])
    except oracledb.DatabaseError as exc:
        error = exc.args[0]
        if getattr(error, "code", None) in (942, 4043):
            return None
        raise


def _oracledb_connect_kwargs(paths: LoadPaths, env: Mapping[str, str]) -> dict[str, Any]:
    connect_alias = env.get("OCI_CIS_ADB_CONNECT_ALIAS", DEFAULT_CONNECT_ALIAS)
    user = env.get("OCI_CIS_ADB_USER", "ADMIN")
    password = paths.password_file.read_text(encoding="utf-8").strip()
    wallet_password = _adb_wallet_password(env)
    if (paths.wallet_dir / "ewallet.pem").exists() and not wallet_password:
        raise ValueError(
            "OCI_CIS_ADB_WALLET_PASSWORD_SECRET_OCID is required for python-oracledb Thin mode with mTLS",
        )

    os.environ["TNS_ADMIN"] = paths.wallet_dir.as_posix()
    connect_kwargs: dict[str, Any] = {
        "user": user,
        "password": password,
        "dsn": connect_alias,
        "config_dir": paths.wallet_dir.as_posix(),
        "wallet_location": paths.wallet_dir.as_posix(),
    }
    if wallet_password:
        connect_kwargs["wallet_password"] = wallet_password
    return connect_kwargs


def run_sqlcl_file(sql_file: Path, paths: LoadPaths, env: Mapping[str, str]) -> dict[str, Any]:
    import subprocess

    sqlcl = env.get("OCI_CIS_SQLCL_PATH", "sql")
    connect_alias = env.get("OCI_CIS_ADB_CONNECT_ALIAS", DEFAULT_CONNECT_ALIAS)
    user = env.get("OCI_CIS_ADB_USER", "ADMIN")
    timeout_seconds = int(env.get("OCI_CIS_SQL_TIMEOUT_SECONDS", "240"))
    password = paths.password_file.read_text(encoding="utf-8").strip()

    sqlcl_env = os.environ.copy()
    sqlcl_env["TNS_ADMIN"] = paths.wallet_dir.as_posix()
    stdin = f"connect {user}/{password}@{connect_alias}\n@{sql_file}\nexit\n"
    completed = subprocess.run(
        [sqlcl, "-s", "-L", "/nolog"],
        input=stdin,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=sqlcl_env,
        timeout=timeout_seconds,
        check=False,
    )
    redacted_output = completed.stdout.replace(password, "[REDACTED]")
    _emit_log("sqlcl_file_complete", sql_file=sql_file.name, exit_code=completed.returncode, output_tail=redacted_output[-3000:])
    return {"exitCode": completed.returncode, "outputTail": redacted_output[-3000:]}


def _iter_executable_sql(sql_text: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    skipping_select = False
    in_plsql = False

    for line in sql_text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if not stripped or stripped.startswith("--"):
            continue
        if lower.startswith(("set ", "whenever ", "prompt ")):
            continue
        if lower.startswith("exit"):
            break
        if stripped == "/" and in_plsql:
            statement = "\n".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            in_plsql = False
            continue
        if not current and lower.startswith("select "):
            skipping_select = True
        if skipping_select:
            if stripped.endswith(";"):
                skipping_select = False
            continue
        if not current and lower.startswith(("begin", "declare")):
            in_plsql = True
        current.append(line)
        if not in_plsql and stripped.endswith(";"):
            statement = "\n".join(current).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            current = []

    if current:
        statement = "\n".join(current).strip().rstrip(";").strip()
        if statement:
            statements.append(statement)
    return statements


def _object_storage_client() -> object:
    if oci is None:
        raise RuntimeError("oci package is required in OCI Function runtime")
    signer = oci.auth.signers.get_resource_principals_signer()
    return oci.object_storage.ObjectStorageClient({"region": signer.region}, signer=signer)


def _list_objects(client: object, namespace: str, bucket: str, prefix: str) -> list[str]:
    objects: list[str] = []
    start = None
    while True:
        response_obj = client.list_objects(namespace, bucket, prefix=prefix, start=start)
        objects.extend(item.name for item in response_obj.data.objects)
        start = response_obj.data.next_start_with
        if not start:
            return objects


def _download_object(client: object, namespace: str, bucket: str, object_name: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    response_obj = client.get_object(namespace, bucket, object_name)
    with target.open("wb") as handle:
        for chunk in response_obj.data.raw.stream(1024 * 1024, decode_content=False):
            handle.write(chunk)


def _get_namespace(client: object) -> str:
    return str(client.get_namespace().data)


def _adb_password(env: Mapping[str, str]) -> str:
    direct = env.get("OCI_CIS_ADB_PASSWORD", "").strip()
    if direct:
        return direct
    password_file = env.get("OCI_CIS_ADB_PASSWORD_FILE", "").strip()
    if password_file:
        value = Path(password_file).read_text(encoding="utf-8").strip()
        if value:
            return value
    secret_ocid = env.get("OCI_CIS_ADB_PASSWORD_SECRET_OCID", "").strip()
    if secret_ocid:
        return _read_secret(secret_ocid)
    raise ValueError("ADB password source is required: use OCI_CIS_ADB_PASSWORD_SECRET_OCID for OCI")


def _adb_wallet_password(env: Mapping[str, str]) -> str | None:
    direct = env.get("OCI_CIS_ADB_WALLET_PASSWORD", "").strip()
    if direct:
        return direct
    password_file = env.get("OCI_CIS_ADB_WALLET_PASSWORD_FILE", "").strip()
    if password_file:
        value = Path(password_file).read_text(encoding="utf-8").strip()
        if value:
            return value
    secret_ocid = env.get("OCI_CIS_ADB_WALLET_PASSWORD_SECRET_OCID", "").strip()
    if secret_ocid:
        return _read_secret(secret_ocid)
    return None


def _read_secret(secret_ocid: str) -> str:
    if oci is None:
        raise RuntimeError("oci package is required to read Vault secrets")
    signer = oci.auth.signers.get_resource_principals_signer()
    client = oci.secrets.SecretsClient({"region": signer.region}, signer=signer)
    bundle = client.get_secret_bundle(secret_ocid).data
    content = bundle.secret_bundle_content.content
    return base64.b64decode(content).decode("utf-8").strip()


def _load_payload(data: io.BytesIO | None) -> dict[str, Any]:
    if data is None:
        return {}
    raw = data.getvalue()
    if not raw:
        return {}
    loaded = json.loads(raw.decode("utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("request body must be a JSON object")
    return loaded


def _ctx_config(ctx: object | None) -> dict[str, Any]:
    if ctx is None or not hasattr(ctx, "Config"):
        return {}
    cfg = ctx.Config()
    return dict(cfg) if isinstance(cfg, Mapping) else {}


def _validated_run_id(value: object) -> str:
    run_id = str(value or "").strip()
    if not RUN_ID_PATTERN.match(run_id):
        raise ValueError("runId must be 1-120 chars and contain only letters, numbers, dot, underscore, or dash")
    return run_id


def _first(*values: object) -> object | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _required(value: object, name: str) -> str:
    if value is None or not str(value).strip():
        raise ValueError(f"{name} is required")
    return str(value).strip()


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _split_regions(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _bool_value(value: object, *, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _emit_log(event: str, **fields: Any) -> None:
    record = {
        "component": "adb-sql-loader-function",
        "event": event,
        "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        **fields,
    }
    logging.getLogger().info(json.dumps(record, sort_keys=True))
