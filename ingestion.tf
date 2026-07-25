resource "oci_functions_function" "object_event_loader" {
  application_id     = oci_functions_application.workload.id
  display_name       = "object-storage-event-loader"
  image              = local.object_event_loader_image
  memory_in_mbs      = 256
  timeout_in_seconds = 120
  freeform_tags      = local.tags

  config = {
    OCI_CIS_OBJECT_BUCKET                             = oci_objectstorage_bucket.reports.name
    OCI_CIS_VALIDATE_COMPANION_MARKER                 = "true"
    OCI_CIS_SQL_LOADER_FUNCTION_ID                    = oci_functions_function.adb_sql_loader.id
    OCI_CIS_SQL_LOADER_INVOKE_ENDPOINT                = oci_functions_function.adb_sql_loader.invoke_endpoint
    OCI_CIS_SQL_LOADER_INVOKE_TYPE                    = "detached"
    OCI_CIS_SQL_LOADER_CLIENT_CONNECT_TIMEOUT_SECONDS = "5"
    OCI_CIS_SQL_LOADER_CLIENT_READ_TIMEOUT_SECONDS    = "15"
  }
}

resource "oci_functions_function" "adb_sql_loader" {
  application_id     = oci_functions_application.workload.id
  display_name       = "adb-sql-loader"
  image              = local.adb_sql_loader_image
  memory_in_mbs      = 2048
  timeout_in_seconds = 300
  freeform_tags      = local.tags

  config = {
    OCI_CIS_OBJECT_BUCKET                   = oci_objectstorage_bucket.reports.name
    OCI_CIS_TENANCY_ID                      = var.tenancy_ocid
    OCI_CIS_SCANNER_VERSION                 = "3.3.0"
    OCI_CIS_BENCHMARK_VERSION               = "3.0.0"
    OCI_CIS_REQUESTED_REGIONS               = var.cis_regions
    OCI_CIS_ADB_USER                        = "ADMIN"
    OCI_CIS_ADB_TARGET_SCHEMA               = "OCI_CIS_APP"
    OCI_CIS_ADB_CONNECT_ALIAS               = local.adb_tns_alias
    OCI_CIS_ADB_PASSWORD_SECRET_OCID        = oci_vault_secret.adb_admin_password.id
    OCI_CIS_ADB_WALLET_PASSWORD_SECRET_OCID = oci_vault_secret.adb_wallet_password.id
    OCI_CIS_ADB_WALLET_CHUNK_SECRET_OCIDS   = join(",", [for secret in oci_vault_secret.adb_wallet_fragment : secret.id])
    OCI_CIS_SQL_EXECUTOR                    = "oracledb"
    OCI_CIS_RECONCILE_ABSENT                = "true"
  }

  depends_on = [oci_database_autonomous_database.cis]
}

resource "oci_events_rule" "report_uploaded" {
  compartment_id = var.compartment_id
  display_name   = "${var.name_prefix}-cis-report-ready"
  description    = "Invokes the Object Storage event loader; the loader only processes CIS run completion markers."
  is_enabled     = true
  freeform_tags  = local.tags

  condition = jsonencode({
    eventType = ["com.oraclecloud.objectstorage.createobject"]
    data = {
      additionalDetails = {
        bucketName = [oci_objectstorage_bucket.reports.name]
      }
    }
  })

  actions {
    action {
      action_type = "FAAS"
      description = "Process a completed CIS report run and invoke the ADB SQL loader"
      function_id = oci_functions_function.object_event_loader.id
      is_enabled  = true
    }
  }
}

resource "oci_identity_dynamic_group" "object_event_loader" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_object_event_loader_dg"
  description    = "Object Storage event loader Function identity"
  matching_rule  = "ALL {resource.type = 'fnfunc', resource.id = '${oci_functions_function.object_event_loader.id}'}"
}

resource "oci_identity_dynamic_group" "adb_sql_loader" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_adb_sql_loader_dg"
  description    = "ADB SQL loader Function identity"
  matching_rule  = "ALL {resource.type = 'fnfunc', resource.id = '${oci_functions_function.adb_sql_loader.id}'}"
}

resource "oci_identity_dynamic_group" "adb" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_adb_dg"
  description    = "CIS Autonomous Database resource-principal identity"
  matching_rule  = "ALL {resource.type = 'autonomousdatabase', resource.id = '${oci_database_autonomous_database.cis.id}'}"
}

resource "oci_identity_policy" "object_event_loader" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_object_event_loader_policy"
  description    = "Lets the Object Storage event loader validate completion markers and invoke the SQL loader"

  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.object_event_loader.name} to read buckets in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.object_event_loader.name} to read objects in compartment id ${var.compartment_id} where target.bucket.name = '${oci_objectstorage_bucket.reports.name}'",
    "Allow dynamic-group ${oci_identity_dynamic_group.object_event_loader.name} to use fn-invocation in compartment id ${var.compartment_id}",
  ]
}

resource "oci_identity_policy" "adb_sql_loader" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_adb_sql_loader_policy"
  description    = "Lets the ADB SQL loader read completed CIS runs and runtime database credentials"

  statements = concat([
    "Allow dynamic-group ${oci_identity_dynamic_group.adb_sql_loader.name} to read buckets in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.adb_sql_loader.name} to manage objects in compartment id ${var.compartment_id} where target.bucket.name = '${oci_objectstorage_bucket.reports.name}'",
    "Allow dynamic-group ${oci_identity_dynamic_group.adb_sql_loader.name} to read secret-bundles in compartment id ${var.compartment_id} where target.secret.id = '${oci_vault_secret.adb_admin_password.id}'",
    "Allow dynamic-group ${oci_identity_dynamic_group.adb_sql_loader.name} to read secret-bundles in compartment id ${var.compartment_id} where target.secret.id = '${oci_vault_secret.adb_wallet_password.id}'",
    ], [
    for secret in oci_vault_secret.adb_wallet_fragment :
    "Allow dynamic-group ${oci_identity_dynamic_group.adb_sql_loader.name} to read secret-bundles in compartment id ${var.compartment_id} where target.secret.id = '${secret.id}'"
  ])
}

resource "oci_identity_policy" "adb" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_adb_policy"
  description    = "Lets the CIS Autonomous Database resource principal read staged reports"

  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.adb.name} to read buckets in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.adb.name} to read objects in compartment id ${var.compartment_id} where target.bucket.name = '${oci_objectstorage_bucket.reports.name}'",
  ]
}
