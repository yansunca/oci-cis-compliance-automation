import io
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import oci
from fdk import response


LOG = logging.getLogger()
LOG.setLevel(logging.INFO)


def _bool(name: str) -> bool:
    return os.environ.get(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required function configuration: {name}")
    return value


def _has_active_cis_run(client: oci.container_instances.ContainerInstanceClient, compartment_id: str) -> bool:
    """Avoid two expensive tenancy scans running concurrently.

    A completed Container Instance is deliberately not restarted. A fresh instance is
    created for every run, which provides an isolated resource-principal identity and
    a unique output prefix.
    """
    result = oci.pagination.list_call_get_all_results(
        client.list_container_instances,
        compartment_id=compartment_id,
    )
    active_states = {"CREATING", "ACTIVE", "UPDATING"}
    for item in result.data:
        if not item.display_name.startswith("cis-runner-"):
            continue
        if item.lifecycle_state == "CREATING":
            return True
        if item.lifecycle_state != "ACTIVE":
            continue

        # A completed one-shot Container Instance can remain ACTIVE while its
        # only container is INACTIVE. Check the container state so it does not
        # prevent every later scheduled run.
        instance = client.get_container_instance(item.id).data
        containers = [client.get_container(container.container_id).data for container in instance.containers]
        if any(container.lifecycle_state in active_states for container in containers):
            return True
    return False


def _handler(ctx, data: io.BytesIO = None):
    signer = oci.auth.signers.get_resource_principals_signer()
    config = {"region": signer.region, "tenancy": signer.tenancy_id}
    client = oci.container_instances.ContainerInstanceClient(config, signer=signer)

    compartment_id = _required("COMPARTMENT_ID")
    if _bool("ACTIVE_RUN_GUARD") and _has_active_cis_run(client, compartment_id):
        message = {"status": "skipped", "reason": "a CIS Container Instance is already active"}
        LOG.warning(message["reason"])
        return response.Response(ctx, response_data=json.dumps(message), status_code=409)

    run_prefix = os.environ.get("RUN_PREFIX", "CIS-CI").strip() or "CIS-CI"
    run_id = f"{run_prefix}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    container_environment = {
        "RUN_ID": run_id,
        "OUTPUT_BUCKET": _required("OUTPUT_BUCKET"),
        "OBJECT_PREFIX": os.environ.get("OBJECT_PREFIX", ""),
        "CIS_REGIONS": os.environ.get("CIS_REGIONS", "All"),
        "CIS_LEVEL": os.environ.get("CIS_LEVEL", "2"),
        "CIS_INCLUDE_OBP": os.environ.get("CIS_INCLUDE_OBP", "false"),
        "CIS_INCLUDE_RAW": os.environ.get("CIS_INCLUDE_RAW", "false"),
        "CIS_REDACT_OUTPUT": os.environ.get("CIS_REDACT_OUTPUT", "false"),
        "CIS_ALL_RESOURCES": os.environ.get("CIS_ALL_RESOURCES", "true"),
        "CIS_DEBUG": os.environ.get("CIS_DEBUG", "false"),
    }

    vnic = oci.container_instances.models.CreateContainerVnicDetails(
        subnet_id=_required("SUBNET_ID"),
        is_public_ip_assigned=_bool("ASSIGN_PUBLIC_IP"),
    )
    network_security_group_id = os.environ.get("NETWORK_SECURITY_GROUP_ID")
    if network_security_group_id:
        vnic.nsg_ids = [network_security_group_id]

    details = oci.container_instances.models.CreateContainerInstanceDetails(
        compartment_id=compartment_id,
        availability_domain=_required("AVAILABILITY_DOMAIN"),
        display_name=f"cis-runner-{run_id}",
        shape=_required("CONTAINER_SHAPE"),
        shape_config=oci.container_instances.models.CreateContainerInstanceShapeConfigDetails(
            ocpus=float(os.environ.get("CONTAINER_OCPUS", "2")),
            memory_in_gbs=float(os.environ.get("CONTAINER_MEMORY_IN_GBS", "16")),
        ),
        container_restart_policy="NEVER",
        containers=[
            oci.container_instances.models.CreateContainerDetails(
                display_name="cis-runner",
                image_url=_required("CIS_RUNNER_IMAGE"),
                environment_variables=container_environment,
                is_resource_principal_disabled=False,
            )
        ],
        vnics=[vnic],
        freeform_tags={"Workload": "cis-compliance-automation", "RunId": run_id},
    )

    created = client.create_container_instance(details).data
    body = {"status": "started", "run_id": run_id, "container_instance_id": created.id}
    LOG.info("Created CIS Container Instance %s for run %s", created.id, run_id)
    return response.Response(ctx, response_data=json.dumps(body), status_code=202)


def handler(ctx, data: io.BytesIO = None):
    """Return actionable, non-secret diagnostics when the controller cannot start a run."""
    try:
        return _handler(ctx, data)
    except oci.exceptions.ServiceError as error:
        diagnostic = {
            "status": "error",
            "error_type": "oci_service_error",
            "service_code": error.code,
            "message": error.message,
            "opc_request_id": error.request_id,
        }
        LOG.exception("CIS controller OCI service error")
        print(json.dumps({"cis_controller_error": diagnostic}), flush=True)
        return response.Response(ctx, response_data=json.dumps(diagnostic), status_code=500)
    except Exception as error:
        diagnostic = {
            "status": "error",
            "error_type": type(error).__name__,
            "message": str(error),
        }
        LOG.exception("CIS controller failed")
        print(json.dumps({"cis_controller_error": diagnostic}), flush=True)
        return response.Response(ctx, response_data=json.dumps(diagnostic), status_code=500)
