output "tenancy_namespace" {
  description = "OCIR tenancy namespace; use it when pushing the three images."
  value       = oci_artifacts_container_repository.controller.namespace
}

output "controller_image" {
  value = local.controller_image
}

output "runner_image" {
  value = local.runner_image
}

output "ingester_image" {
  value = local.ingester_image
}

output "report_bucket" {
  value = oci_objectstorage_bucket.reports.name
}

output "function_invocation_log" {
  description = "OCI Logging service log that records controller Function invocations."
  value       = oci_logging_log.function_invocations.id
}

output "controller_invoke_endpoint" {
  value = oci_functions_function.controller.invoke_endpoint
}

output "resource_schedule_ocid" {
  value = oci_resource_scheduler_schedule.controller.id
}

output "report_ingestion_function" {
  description = "Function invoked by the Object Storage report-create event."
  value       = oci_functions_function.ingester.id
}

output "report_upload_event_rule" {
  value = oci_events_rule.report_uploaded.id
}

output "autonomous_database_id" {
  value = oci_database_autonomous_database.cis.id
}

output "autonomous_database_public_low_connect_string" {
  description = "Public mTLS connect string for the LOW database service."
  value       = oci_database_autonomous_database.cis.connection_strings[0].low
}

output "cis_results_table" {
  description = "Single ADB table populated by the report-ingestion Function."
  value       = "ADMIN.CIS_RESULTS"
}
