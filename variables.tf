variable "tenancy_ocid" {
  description = "OCID of the OCI tenancy. IAM policies are created in this tenancy."
  type        = string
}

variable "compartment_id" {
  description = "Dedicated workload compartment OCID. Do not place unrelated Container Instances here because the CIS runner dynamic group covers Container Instances in this compartment."
  type        = string
}

variable "region" {
  description = "OCI region identifier, for example us-ashburn-1."
  type        = string
}

variable "region_key" {
  description = "OCIR region key, for example iad for us-ashburn-1."
  type        = string
}

variable "name_prefix" {
  description = "Short, lowercase prefix used in resource names."
  type        = string
  default     = "cis-auto"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,18}$", var.name_prefix))
    error_message = "name_prefix must be 3-19 lowercase letters, digits, or hyphens and start with a letter."
  }
}

variable "existing_private_subnet_id" {
  description = "OCID of an existing private subnet for OCI Functions and one-shot Container Instances. It must provide egress to OCIR, Object Storage, and OCI API endpoints."
  type        = string
}

variable "existing_network_security_group_id" {
  description = "Optional OCID of an existing NSG to attach to the Function application. Leave null to rely on the subnet's security lists."
  type        = string
  default     = null
}

variable "scanner_subnet_id" {
  description = "Optional subnet OCID for scanner Container Instances. Defaults to existing_private_subnet_id. Use this only when the scanner needs a different egress subnet from Functions."
  type        = string
  default     = ""
}

variable "scanner_network_security_group_id" {
  description = "Optional NSG OCID for scanner Container Instances. Defaults to existing_network_security_group_id when empty."
  type        = string
  default     = ""
}

variable "schedule_cron" {
  description = "UNIX cron expression, evaluated in UTC, for Resource Scheduler."
  type        = string
  default     = "0 2 * * 0"
}

variable "image_tag" {
  description = "Immutable tag to deploy for the controller and runner images. Change this on each release."
  type        = string
  default     = "v1"
}

variable "loader_image_tag" {
  description = "Immutable tag to deploy for the Object Storage event loader and ADB SQL loader Function images."
  type        = string
  default     = "v1"
}

variable "container_shape" {
  description = "OCI Container Instance shape used for each CIS scan."
  type        = string
  default     = "CI.Standard.A1.Flex"
}

variable "cis_regions" {
  description = "CIS script region selection. Use All or a comma-separated list such as us-ashburn-1,us-phoenix-1."
  type        = string
  default     = "All"
}

variable "cis_level" {
  description = "CIS benchmark level to run."
  type        = number
  default     = 2

  validation {
    condition     = contains([1, 2], var.cis_level)
    error_message = "cis_level must be 1 or 2."
  }
}

variable "cis_include_obp" {
  description = "Also run Oracle best-practice checks. This increases run time."
  type        = bool
  default     = false
}

variable "cis_include_raw" {
  description = "Include raw discovery output in the zip package. This can materially increase package size."
  type        = bool
  default     = false
}

variable "cis_redact_output" {
  description = "Redact OCIDs in CIS CSV/JSON output before packaging it."
  type        = bool
  default     = false
}

variable "cis_all_resources" {
  description = "Include broader resource evidence used for product/tag mapping."
  type        = bool
  default     = true
}

variable "cis_debug" {
  description = "Enable CIS script debug mode inside the scanner container."
  type        = bool
  default     = false
}

variable "object_prefix" {
  description = "Optional Object Storage prefix before each run_id. Leave empty for <run_id>/... layout."
  type        = string
  default     = ""
}

variable "run_prefix" {
  description = "Prefix for generated run IDs. The controller appends UTC timestamp and a short unique suffix."
  type        = string
  default     = "CIS-CI"
}

variable "assign_public_ip" {
  description = "Assign a public IP to each Container Instance VNIC. Prefer false when the subnet has private egress to OCIR, Object Storage, and OCI APIs."
  type        = bool
  default     = false
}

variable "container_ocpus" {
  description = "OCPUs for each one-shot CIS Container Instance."
  type        = number
  default     = 2
}

variable "container_memory_in_gbs" {
  description = "Memory in GB for each one-shot CIS Container Instance."
  type        = number
  default     = 16
}

variable "freeform_tags" {
  description = "Optional tags added to all supported resources."
  type        = map(string)
  default     = {}
}

variable "adb_admin_password" {
  description = "Administrator password for the new Autonomous Database. Terraform stores it as sensitive state and copies it into OCI Vault for runtime use."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.adb_admin_password) >= 12 && can(regex("[A-Z]", var.adb_admin_password)) && can(regex("[a-z]", var.adb_admin_password)) && can(regex("[0-9]", var.adb_admin_password)) && can(regex("[^[:alnum:]]", var.adb_admin_password))
    error_message = "adb_admin_password must be at least 12 characters and include uppercase, lowercase, numeric, and special characters."
  }
}

variable "adb_db_name" {
  description = "Database name for the Autonomous Database."
  type        = string
  default     = "CISAUTOMATION"

  validation {
    condition     = can(regex("^[A-Z][A-Z0-9]{0,13}$", var.adb_db_name))
    error_message = "adb_db_name must be 1-14 uppercase alphanumeric characters and start with a letter."
  }
}

variable "adb_ecpu_count" {
  description = "Initial ECPU count for the paid Autonomous AI Database Serverless instance."
  type        = number
  default     = 2

  validation {
    condition     = var.adb_ecpu_count >= 2
    error_message = "adb_ecpu_count must be at least 2 for this paid Autonomous AI Database Serverless instance."
  }
}

variable "adb_data_storage_size_in_tbs" {
  description = "Initial storage allocation in TB for the paid Autonomous Database Serverless instance."
  type        = number
  default     = 1

  validation {
    condition     = var.adb_data_storage_size_in_tbs >= 1
    error_message = "adb_data_storage_size_in_tbs must be at least 1."
  }
}


variable "adb_private_endpoint_subnet_id" {
  description = "Optional subnet OCID for a private-endpoint Autonomous Database. Leave empty to create the database with secure public access."
  type        = string
  default     = ""
}

variable "adb_private_endpoint_nsg_ids" {
  description = "Optional NSG OCIDs for the private-endpoint Autonomous Database. Used only when adb_private_endpoint_subnet_id is set."
  type        = list(string)
  default     = []
}

variable "adb_private_endpoint_label" {
  description = "Optional private endpoint label. Used only when adb_private_endpoint_subnet_id is set."
  type        = string
  default     = ""
}

variable "adb_service_level" {
  description = "mTLS database service profile used by the ingestion Function."
  type        = string
  default     = "LOW"

  validation {
    condition     = contains(["LOW", "MEDIUM", "HIGH"], var.adb_service_level)
    error_message = "adb_service_level must be LOW, MEDIUM, or HIGH."
  }
}
