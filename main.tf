data "oci_identity_availability_domains" "current" {
  compartment_id = var.tenancy_ocid
}

data "oci_objectstorage_namespace" "current" {
  compartment_id = var.compartment_id
}

locals {
  tags = merge(var.freeform_tags, {
    ManagedBy = "Terraform"
    Workload  = "cis-compliance-automation"
  })

  controller_image          = "${var.region_key}.ocir.io/${oci_artifacts_container_repository.controller.namespace}/${oci_artifacts_container_repository.controller.display_name}:${var.image_tag}"
  runner_image              = "${var.region_key}.ocir.io/${oci_artifacts_container_repository.runner.namespace}/${oci_artifacts_container_repository.runner.display_name}:${var.image_tag}"
  object_event_loader_image = "${var.region_key}.ocir.io/${oci_artifacts_container_repository.object_event_loader.namespace}/${oci_artifacts_container_repository.object_event_loader.display_name}:${var.loader_image_tag}"
  adb_sql_loader_image      = "${var.region_key}.ocir.io/${oci_artifacts_container_repository.adb_sql_loader.namespace}/${oci_artifacts_container_repository.adb_sql_loader.display_name}:${var.loader_image_tag}"
}

resource "oci_objectstorage_bucket" "reports" {
  compartment_id        = var.compartment_id
  namespace             = data.oci_objectstorage_namespace.current.namespace
  name                  = "${var.name_prefix}-cis-reports"
  access_type           = "NoPublicAccess"
  object_events_enabled = true
  versioning            = "Enabled"
  auto_tiering          = "Disabled"
  freeform_tags         = local.tags
}

resource "oci_artifacts_container_repository" "controller" {
  compartment_id = var.compartment_id
  display_name   = "${var.name_prefix}-controller"
  is_public      = false
  freeform_tags  = local.tags
}

resource "oci_artifacts_container_repository" "runner" {
  compartment_id = var.compartment_id
  display_name   = "${var.name_prefix}-runner"
  is_public      = false
  freeform_tags  = local.tags
}

resource "oci_artifacts_container_repository" "object_event_loader" {
  compartment_id = var.compartment_id
  display_name   = "${var.name_prefix}-object-event-loader"
  is_public      = false
  freeform_tags  = local.tags
}

resource "oci_artifacts_container_repository" "adb_sql_loader" {
  compartment_id = var.compartment_id
  display_name   = "${var.name_prefix}-adb-sql-loader"
  is_public      = false
  freeform_tags  = local.tags
}

resource "oci_functions_application" "workload" {
  compartment_id             = var.compartment_id
  display_name               = "${var.name_prefix}-functions"
  subnet_ids                 = [var.existing_private_subnet_id]
  network_security_group_ids = var.existing_network_security_group_id == null ? null : [var.existing_network_security_group_id]
  shape                      = "GENERIC_X86"
  freeform_tags              = local.tags
}

resource "oci_logging_log_group" "functions" {
  compartment_id = var.compartment_id
  display_name   = "${var.name_prefix}-function-logs"
  description    = "Invocation logs for CIS controller and report-ingestion Functions"
  freeform_tags  = local.tags
}

resource "oci_logging_log" "function_invocations" {
  display_name       = "${var.name_prefix}-function-invocations"
  log_group_id       = oci_logging_log_group.functions.id
  log_type           = "SERVICE"
  is_enabled         = true
  retention_duration = 30
  freeform_tags      = local.tags

  configuration {
    compartment_id = var.compartment_id

    source {
      category    = "invoke"
      resource    = oci_functions_application.workload.id
      service     = "functions"
      source_type = "OCISERVICE"
    }
  }
}

resource "oci_functions_function" "controller" {
  application_id     = oci_functions_application.workload.id
  display_name       = "cis-container-controller"
  image              = local.controller_image
  memory_in_mbs      = 512
  timeout_in_seconds = 300
  freeform_tags      = local.tags

  config = {
    COMPARTMENT_ID            = var.compartment_id
    AVAILABILITY_DOMAIN       = data.oci_identity_availability_domains.current.availability_domains[0].name
    SUBNET_ID                 = var.scanner_subnet_id == "" ? var.existing_private_subnet_id : var.scanner_subnet_id
    NETWORK_SECURITY_GROUP_ID = var.scanner_network_security_group_id == "" ? (var.existing_network_security_group_id == null ? "" : var.existing_network_security_group_id) : var.scanner_network_security_group_id
    CIS_RUNNER_IMAGE          = local.runner_image
    OUTPUT_BUCKET             = oci_objectstorage_bucket.reports.name
    CIS_REGIONS               = var.cis_regions
    CIS_LEVEL                 = tostring(var.cis_level)
    CIS_INCLUDE_OBP           = tostring(var.cis_include_obp)
    CIS_INCLUDE_RAW           = tostring(var.cis_include_raw)
    CIS_REDACT_OUTPUT         = tostring(var.cis_redact_output)
    CIS_ALL_RESOURCES         = tostring(var.cis_all_resources)
    CIS_DEBUG                 = tostring(var.cis_debug)
    OBJECT_PREFIX             = var.object_prefix
    RUN_PREFIX                = var.run_prefix
    ASSIGN_PUBLIC_IP          = tostring(var.assign_public_ip)
    CONTAINER_SHAPE           = var.container_shape
    CONTAINER_OCPUS           = tostring(var.container_ocpus)
    CONTAINER_MEMORY_IN_GBS   = tostring(var.container_memory_in_gbs)
    ACTIVE_RUN_GUARD          = "true"
  }
}

resource "oci_resource_scheduler_schedule" "controller" {
  compartment_id     = var.compartment_id
  display_name       = "${var.name_prefix}-cis-schedule"
  description        = "Runs the CIS Container Instance controller Function"
  action             = "START_RESOURCE"
  recurrence_type    = "CRON"
  recurrence_details = var.schedule_cron
  freeform_tags      = local.tags

  resources {
    id = oci_functions_function.controller.id
  }
}

# Resource-principal dynamic groups. The Container Instance group is deliberately limited to a dedicated workload compartment.
resource "oci_identity_dynamic_group" "scheduler" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_scheduler_dg"
  description    = "Resource Scheduler identity for the CIS controller schedule"
  matching_rule  = "ALL {resource.type = 'resourceschedule', resource.id = '${oci_resource_scheduler_schedule.controller.id}'}"
}

resource "oci_identity_dynamic_group" "controller" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_controller_dg"
  description    = "Controller Function identity"
  matching_rule  = "ALL {resource.type = 'fnfunc', resource.id = '${oci_functions_function.controller.id}'}"
}

resource "oci_identity_dynamic_group" "runner" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_runner_dg"
  description    = "CIS Container Instance identities in the dedicated workload compartment"
  matching_rule  = "ALL {resource.type = 'computecontainerinstance', resource.compartment.id = '${var.compartment_id}'}"
}

resource "oci_identity_policy" "scheduler" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_scheduler_policy"
  description    = "Lets this Resource Scheduler schedule invoke the controller Function"

  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.scheduler.name} to manage functions-family in compartment id ${var.compartment_id}",
  ]
}

resource "oci_identity_policy" "controller" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_controller_policy"
  description    = "Lets the controller Function create one-shot CIS Container Instances"

  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.controller.name} to manage compute-container-family in compartment id ${var.compartment_id}",
    "Allow dynamic-group ${oci_identity_dynamic_group.controller.name} to use virtual-network-family in compartment id ${var.compartment_id}",
    "Allow dynamic-group ${oci_identity_dynamic_group.controller.name} to read repos in tenancy",
  ]
}

# These are the read permissions used by the CIS script from the referenced blog. Review them against your enabled CIS checks.
resource "oci_identity_policy" "runner" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_runner_policy"
  description    = "Tenancy read permissions required by the CIS benchmark Container Instance"

  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to inspect all-resources in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read instances in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read load-balancers in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read buckets in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read nat-gateways in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read public-ips in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read file-family in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read instance-configurations in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read network-security-groups in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read resource-availability in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read audit-events in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read users in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read vss-family in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read usage-budgets in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read usage-reports in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read data-safe-family in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read vaults in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read keys in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read tag-namespaces in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to read repos in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to use virtual-network-family in compartment id ${var.compartment_id}",
    "Allow dynamic-group ${oci_identity_dynamic_group.runner.name} to manage objects in compartment id ${var.compartment_id} where target.bucket.name = '${oci_objectstorage_bucket.reports.name}'",
  ]
}
