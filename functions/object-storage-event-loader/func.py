"""Object Storage completion-marker event handler for OCI CIS report runs.

The scanner uploads many report files. This Function only reacts to a final
success marker so downstream loading does not start from a partial report set.
The handler still requires `run_ready.json` as companion run metadata.
"""

from __future__ import annotations

import io
import json
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Mapping
from urllib.parse import unquote

try:  # pragma: no cover - exercised in OCI Functions runtime
    from fdk import response
except ImportError:  # pragma: no cover - keeps local unit tests dependency-free
    response = None  # type: ignore[assignment]


TRIGGER_MARKER_NAMES = frozenset({"_SUCCESS", "_SUCCESS.txt"})
COMPANION_MARKER_NAME = "run_ready.json"
DEFAULT_VALIDATE_COMPANION_MARKER = True

logging.basicConfig(level=logging.INFO)
logging.getLogger("oci").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


@dataclass(frozen=True)
class ObjectEvent:
    event_type: str
    bucket_name: str
    namespace: str | None
    object_name: str
    compartment_id: str | None
    event_time: str | None

    @property
    def marker_name(self) -> str:
        return self.object_name.rsplit("/", 1)[-1]

    @property
    def run_prefix(self) -> str:
        if "/" not in self.object_name:
            return self.object_name
        return self.object_name.rsplit("/", 1)[0]

    @property
    def run_id(self) -> str:
        if "/files/" in self.object_name:
            prefix = self.object_name.split("/files/", 1)[0]
            return prefix.rsplit("/", 1)[-1]
        return self.run_prefix.rsplit("/", 1)[-1]

    @property
    def companion_marker_name(self) -> str:
        return COMPANION_MARKER_NAME

    @property
    def companion_object_name(self) -> str:
        return f"{self.run_prefix}/{self.companion_marker_name}"


ObjectExists = Callable[[str, str, str | None], bool]
LoaderInvoker = Callable[[Mapping[str, Any], Mapping[str, str]], Mapping[str, Any] | None]


def handler(ctx: object, data: io.BytesIO | None = None) -> object:
    status_code = 200
    try:
        event = _load_event(data)
        result = handle_event(event)
    except ValueError as exc:
        status_code = 400
        result = {
            "status": "rejected",
            "reason": "invalid_object_storage_event",
            "message": str(exc),
        }
        _emit_log("cis_object_event_rejected", **result)
    payload = json.dumps(result, indent=2, sort_keys=True)

    if response is None:
        return result

    return response.Response(
        ctx,
        response_data=payload,
        status_code=status_code,
        headers={"Content-Type": "application/json"},
    )


def handle_event(
    event: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    object_exists: ObjectExists | None = None,
    loader_invoker: LoaderInvoker | None = None,
) -> dict[str, Any]:
    env = env or os.environ
    object_event = parse_object_event(event)

    expected_bucket = env.get("OCI_CIS_OBJECT_BUCKET", "").strip()
    if expected_bucket and object_event.bucket_name != expected_bucket:
        result = _result("ignored", object_event, reason="bucket_not_configured_for_loader")
        _emit_log("cis_object_event_ignored", **result)
        return result

    if object_event.marker_name not in TRIGGER_MARKER_NAMES:
        result = _result("ignored", object_event, reason="not_completion_marker")
        _emit_log("cis_object_event_ignored", **result)
        return result

    if "/" not in object_event.object_name or not object_event.run_id:
        result = _result("rejected", object_event, reason="marker_not_under_run_id_prefix")
        _emit_log("cis_object_event_rejected", **result)
        return result

    validate_companion = _bool_value(
        env.get("OCI_CIS_VALIDATE_COMPANION_MARKER"),
        default=DEFAULT_VALIDATE_COMPANION_MARKER,
    )
    companion_present = None
    if validate_companion:
        exists = object_exists or _object_exists_with_resource_principal
        companion_present = exists(
            object_event.bucket_name,
            object_event.companion_object_name,
            object_event.namespace,
        )
        if not companion_present:
            result = _result(
                "waiting",
                object_event,
                companionMarker=object_event.companion_object_name,
                companionPresent=False,
                reason="waiting_for_companion_marker",
            )
            _emit_log("cis_run_marker_waiting", **result)
            return result

    result = _result(
        "ready_for_load",
        object_event,
        companionMarker=object_event.companion_object_name,
        companionPresent=companion_present,
        sourcePrefix=f"{object_event.run_prefix}/files/",
        nextAction="Invoke ADB load pipeline for this run prefix.",
    )
    loader_result = _invoke_sql_loader_if_configured(result, env, loader_invoker=loader_invoker)
    if loader_result is not None:
        result["loaderInvocation"] = dict(loader_result)
    _emit_log("cis_run_ready_for_load", **result)
    return result


def parse_object_event(event: Mapping[str, Any]) -> ObjectEvent:
    data = event.get("data")
    if not isinstance(data, Mapping):
        raise ValueError("OCI event payload must include a data object")

    details = data.get("additionalDetails")
    additional = details if isinstance(details, Mapping) else {}

    bucket_name = _first_string(
        additional.get("bucketName"),
        additional.get("bucket_name"),
        data.get("bucketName"),
    )
    object_name = _first_string(
        additional.get("objectName"),
        additional.get("object_name"),
        data.get("resourceName"),
        data.get("objectName"),
        _object_name_from_resource_id(data.get("resourceId")),
    )
    namespace = _first_string(additional.get("namespace"), data.get("namespace"), required=False)

    if not bucket_name:
        raise ValueError("OCI Object Storage event is missing bucketName")
    if not object_name:
        raise ValueError("OCI Object Storage event is missing object name")

    return ObjectEvent(
        event_type=str(event.get("eventType") or event.get("type") or ""),
        bucket_name=bucket_name,
        namespace=namespace,
        object_name=object_name.lstrip("/"),
        compartment_id=_first_string(data.get("compartmentId"), required=False),
        event_time=_first_string(event.get("eventTime"), event.get("time"), required=False),
    )


def _load_event(data: io.BytesIO | None) -> dict[str, Any]:
    if data is None:
        return {}
    raw = data.getvalue()
    if not raw:
        return {}
    loaded = json.loads(raw.decode("utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError("OCI event payload must be a JSON object")
    return loaded


def _object_name_from_resource_id(resource_id: object) -> str | None:
    if not isinstance(resource_id, str) or "/o/" not in resource_id:
        return None
    return unquote(resource_id.rsplit("/o/", 1)[-1])


def _first_string(*values: object, required: bool = True) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    if required:
        return ""
    return None


def _bool_value(value: object, *, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _object_exists_with_resource_principal(
    bucket_name: str,
    object_name: str,
    namespace: str | None,
) -> bool:
    import oci

    signer = oci.auth.signers.get_resource_principals_signer()
    client = oci.object_storage.ObjectStorageClient({"region": signer.region}, signer=signer)
    namespace_name = namespace or client.get_namespace().data

    try:
        client.head_object(namespace_name, bucket_name, object_name)
    except oci.exceptions.ServiceError as exc:
        if exc.status == 404:
            return False
        raise
    return True


def _invoke_sql_loader_if_configured(
    ready_event: Mapping[str, Any],
    env: Mapping[str, str],
    *,
    loader_invoker: LoaderInvoker | None = None,
) -> Mapping[str, Any] | None:
    loader_function_id = env.get("OCI_CIS_SQL_LOADER_FUNCTION_ID", "").strip()
    if not loader_function_id:
        return None

    payload = {
        "runId": ready_event["runId"],
        "bucket": ready_event["bucket"],
        "namespace": ready_event.get("namespace"),
        "sourcePrefix": ready_event["sourcePrefix"],
        "triggerObjectName": ready_event["objectName"],
        "triggerMarkerName": ready_event["markerName"],
        "companionMarker": ready_event["companionMarker"],
        "requestedAction": "load_completed_cis_run_to_adb",
    }
    invoker = loader_invoker or _invoke_oci_function_loader
    loader_result = invoker(payload, env)
    _emit_log(
        "cis_sql_loader_invoked",
        runId=payload["runId"],
        bucket=payload["bucket"],
        sourcePrefix=payload["sourcePrefix"],
        loaderFunctionId=loader_function_id,
        loaderInvocation=loader_result,
    )
    return loader_result


def _invoke_oci_function_loader(payload: Mapping[str, Any], env: Mapping[str, str]) -> Mapping[str, Any]:
    import oci

    loader_function_id = env["OCI_CIS_SQL_LOADER_FUNCTION_ID"].strip()
    invoke_endpoint = env.get("OCI_CIS_SQL_LOADER_INVOKE_ENDPOINT", "").strip()
    invoke_type = env.get("OCI_CIS_SQL_LOADER_INVOKE_TYPE", "detached").strip() or "detached"
    connect_timeout = int(env.get("OCI_CIS_SQL_LOADER_CLIENT_CONNECT_TIMEOUT_SECONDS", "5"))
    read_timeout = int(env.get("OCI_CIS_SQL_LOADER_CLIENT_READ_TIMEOUT_SECONDS", "15"))

    signer = oci.auth.signers.get_resource_principals_signer()
    client_kwargs: dict[str, Any] = {"signer": signer, "timeout": (connect_timeout, read_timeout)}
    if invoke_endpoint:
        client_kwargs["service_endpoint"] = invoke_endpoint

    client = oci.functions.FunctionsInvokeClient({"region": signer.region}, **client_kwargs)
    try:
        response_data = client.invoke_function(
            loader_function_id,
            invoke_function_body=json.dumps(payload, sort_keys=True).encode("utf-8"),
            fn_invoke_type=invoke_type,
        )
    except oci.exceptions.RequestException as exc:
        if invoke_type.lower() == "detached" and _looks_like_client_timeout(exc):
            return {
                "status": "submitted_response_timeout",
                "functionId": loader_function_id,
                "invokeType": invoke_type,
                "message": "Detached loader invocation was submitted but the caller timed out waiting for the invoke response.",
            }
        raise
    headers = getattr(response_data, "headers", {}) or {}
    return {
        "status": "submitted",
        "functionId": loader_function_id,
        "invokeType": invoke_type,
        "opcRequestId": headers.get("opc-request-id"),
    }


def _looks_like_client_timeout(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "timed out" in text or "read timeout" in text or "timeout" in text


def _result(status: str, event: ObjectEvent, **fields: Any) -> dict[str, Any]:
    return {
        "status": status,
        "runId": event.run_id,
        "bucket": event.bucket_name,
        "namespace": event.namespace,
        "objectName": event.object_name,
        "markerName": event.marker_name,
        "eventType": event.event_type,
        "eventTime": event.event_time,
        **fields,
    }


def _emit_log(event_type: str, **fields: Any) -> None:
    record = {
        "timestamp": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "service": "oci-cis-findings-op",
        "component": "object-storage-event-loader",
        "event_type": event_type,
        **fields,
    }
    logging.getLogger().info(json.dumps(record, sort_keys=True))
