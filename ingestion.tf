resource "oci_functions_function" "ingester" {
  application_id     = oci_functions_application.workload.id
  display_name       = "cis-report-ingester"
  image              = local.ingester_image
  memory_in_mbs      = 1024
  timeout_in_seconds = 300
  freeform_tags      = local.tags

  config = {
    REPORT_BUCKET                 = oci_objectstorage_bucket.reports.name
    ADB_ADMIN_PASSWORD_SECRET_ID  = oci_vault_secret.adb_admin_password.id
    ADB_WALLET_CHUNK_SECRET_IDS   = join(",", [for secret in oci_vault_secret.adb_wallet_fragment : secret.id])
    ADB_WALLET_PASSWORD_SECRET_ID = oci_vault_secret.adb_wallet_password.id
    ADB_TNS_ALIAS                 = local.adb_tns_alias
  }

  depends_on = [oci_database_autonomous_database.cis]
}

resource "oci_events_rule" "report_uploaded" {
  compartment_id = var.compartment_id
  display_name   = "${var.name_prefix}-cis-report-uploaded"
  description    = "Invokes the ADB ingester whenever a CIS report is uploaded"
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
      description = "Load a completed CIS report into Autonomous Database"
      function_id = oci_functions_function.ingester.id
      is_enabled  = true
    }
  }
}

resource "oci_identity_dynamic_group" "ingester" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_ingester_dg"
  description    = "CIS report ingestion Function identity"
  matching_rule  = "ALL {resource.type = 'fnfunc', resource.id = '${oci_functions_function.ingester.id}'}"
}

resource "oci_identity_dynamic_group" "adb" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_adb_dg"
  description    = "CIS Autonomous Database resource-principal identity"
  matching_rule  = "ALL {resource.type = 'autonomousdatabase', resource.id = '${oci_database_autonomous_database.cis.id}'}"
}

resource "oci_identity_policy" "ingester" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_ingester_policy"
  description    = "Lets the report-ingestion Function stage and load CIS reports"

  statements = concat([
    "Allow dynamic-group ${oci_identity_dynamic_group.ingester.name} to read buckets in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.ingester.name} to manage objects in compartment id ${var.compartment_id} where target.bucket.name = '${oci_objectstorage_bucket.reports.name}'",
    "Allow dynamic-group ${oci_identity_dynamic_group.ingester.name} to read secret-bundles in compartment id ${var.compartment_id} where target.secret.id = '${oci_vault_secret.adb_admin_password.id}'",
    "Allow dynamic-group ${oci_identity_dynamic_group.ingester.name} to read secret-bundles in compartment id ${var.compartment_id} where target.secret.id = '${oci_vault_secret.adb_wallet_password.id}'",
    ], [
    for secret in oci_vault_secret.adb_wallet_fragment :
    "Allow dynamic-group ${oci_identity_dynamic_group.ingester.name} to read secret-bundles in compartment id ${var.compartment_id} where target.secret.id = '${secret.id}'"
  ])
}

resource "oci_identity_policy" "adb" {
  compartment_id = var.tenancy_ocid
  name           = "${replace(var.name_prefix, "-", "_")}_adb_policy"
  description    = "Lets the CIS Autonomous Database resource principal load staged reports"

  statements = [
    "Allow dynamic-group ${oci_identity_dynamic_group.adb.name} to read buckets in tenancy",
    "Allow dynamic-group ${oci_identity_dynamic_group.adb.name} to read objects in compartment id ${var.compartment_id} where target.bucket.name = '${oci_objectstorage_bucket.reports.name}'",
  ]
}
