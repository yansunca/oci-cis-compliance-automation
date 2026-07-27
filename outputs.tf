output "compartment_id" {
  description = "Deployment compartment OCID."
  value       = var.compartment_id
}

output "region_key" {
  description = "OCIR region key used by this deployment."
  value       = var.region_key
}

output "region" {
  description = "OCI region used by this deployment."
  value       = var.region
}

output "tenancy_namespace" {
  description = "OCIR tenancy namespace; use it when pushing the four images."
  value       = oci_artifacts_container_repository.controller.namespace
}

output "controller_image" {
  value = local.controller_image
}

output "runner_image" {
  value = local.runner_image
}

output "object_event_loader_image" {
  value = local.object_event_loader_image
}

output "adb_sql_loader_image" {
  value = local.adb_sql_loader_image
}

output "report_bucket" {
  value = oci_objectstorage_bucket.reports.name
}

output "function_invocation_log" {
  description = "OCI Logging service log that records Function invocations."
  value       = oci_logging_log.function_invocations.id
}

output "controller_function_id" {
  value = oci_functions_function.controller.id
}

output "controller_invoke_endpoint" {
  value = oci_functions_function.controller.invoke_endpoint
}

output "resource_schedule_ocid" {
  value = oci_resource_scheduler_schedule.controller.id
}

output "object_event_loader_function" {
  description = "Function invoked by Object Storage create-object events. It processes only CIS completion markers."
  value       = oci_functions_function.object_event_loader.id
}

output "adb_sql_loader_function" {
  description = "Function that loads completed CIS runs into the Autonomous Database canonical schema."
  value       = oci_functions_function.adb_sql_loader.id
}

output "report_upload_event_rule" {
  value = oci_events_rule.report_uploaded.id
}

output "autonomous_database_id" {
  value = oci_database_autonomous_database.cis.id
}

output "autonomous_database_low_connect_string" {
  description = "mTLS connect string for the LOW database service."
  value       = oci_database_autonomous_database.cis.connection_strings[0].low
}

output "adb_migration_source" {
  description = "SQL migrations to install before importing the APEX application."
  value       = "database/migrations"
}

output "apex_application_export" {
  description = "APEX application export to import into the Autonomous Database APEX workspace."
  value       = "apex/export/f100_oci_cis_findings_operations_demo.sql"
}


output "dns_resolver_inbound_endpoint_ip" {
  description = "Private IP for the optional OCI DNS Resolver inbound endpoint. Configure customer/VPN DNS conditional forwarding to this IP."
  value       = try(oci_dns_resolver_endpoint.private_adb_inbound[0].listening_address, null)
}

output "dns_resolver_inbound_endpoint_id" {
  description = "OCID of the optional OCI DNS Resolver inbound endpoint."
  value       = try(oci_dns_resolver_endpoint.private_adb_inbound[0].id, null)
}

output "registry_host" {
  description = "OCIR registry host used for image URIs."
  value       = local.registry_host
}
