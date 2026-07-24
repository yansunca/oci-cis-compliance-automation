locals {
  adb_tns_alias = "${lower(var.adb_db_name)}_${lower(var.adb_service_level)}"

  # OCI Vault limits a secret's content to 25,600 characters. The Base64
  # wallet is split into encrypted fragments and reassembled in Function /tmp.
  adb_wallet_fragment_size = 16000
  adb_wallet_fragments = [
    for offset in [0, 16000, 32000] : (
      length(substr(oci_database_autonomous_database_wallet.cis.content, offset, local.adb_wallet_fragment_size)) > 0
      ? substr(oci_database_autonomous_database_wallet.cis.content, offset, local.adb_wallet_fragment_size)
      : "."
    )
  ]
}

resource "oci_kms_vault" "cis" {
  compartment_id = var.compartment_id
  display_name   = "${var.name_prefix}-vault"
  vault_type     = "DEFAULT"
}

resource "oci_kms_key" "cis" {
  compartment_id      = var.compartment_id
  display_name        = "${var.name_prefix}-adb-password-key"
  management_endpoint = oci_kms_vault.cis.management_endpoint
  protection_mode     = "SOFTWARE"

  key_shape {
    algorithm = "AES"
    length    = 32
  }
}

resource "oci_vault_secret" "adb_admin_password" {
  compartment_id = var.compartment_id
  secret_name    = "${var.name_prefix}-adb-admin-password"
  description    = "Administrator password for the CIS Autonomous Database"
  vault_id       = oci_kms_vault.cis.id
  key_id         = oci_kms_key.cis.id

  secret_content {
    content_type = "BASE64"
    content      = base64encode(var.adb_admin_password)
  }
}

resource "random_password" "adb_wallet" {
  length  = 32
  special = false
}

resource "oci_database_autonomous_database" "cis" {
  compartment_id = var.compartment_id
  db_name        = var.adb_db_name
  display_name   = "${var.name_prefix}-cis-results"
  db_workload    = "OLTP"
  source         = "NONE"
  admin_password = var.adb_admin_password
  # New Autonomous AI Databases use the ECPU compute model. OCPU is a legacy
  # model and OCI no longer accepts it for new database creation.
  compute_model               = "ECPU"
  compute_count               = var.adb_ecpu_count
  data_storage_size_in_tbs    = var.adb_data_storage_size_in_tbs
  is_auto_scaling_enabled     = true
  is_free_tier                = false
  is_mtls_connection_required = true
  license_model               = "LICENSE_INCLUDED"
  subnet_id                   = null
  nsg_ids                     = []
  # OCI switches an existing private-endpoint database to public when this
  # label is reset to an empty string.
  private_endpoint_label = ""
  freeform_tags          = local.tags
}

resource "oci_database_autonomous_database_wallet" "cis" {
  autonomous_database_id = oci_database_autonomous_database.cis.id
  password               = random_password.adb_wallet.result
  base64_encode_content  = true
  generate_type          = "SINGLE"

  lifecycle {
    replace_triggered_by = [oci_database_autonomous_database.cis]
  }
}

resource "oci_vault_secret" "adb_wallet_fragment" {
  count = length(local.adb_wallet_fragments)

  compartment_id = var.compartment_id
  secret_name    = "${var.name_prefix}-adb-wallet-${count.index + 1}"
  description    = "mTLS wallet fragment ${count.index + 1} for the CIS Autonomous Database"
  vault_id       = oci_kms_vault.cis.id
  key_id         = oci_kms_key.cis.id

  secret_content {
    content_type = "BASE64"
    content      = sensitive(base64encode(local.adb_wallet_fragments[count.index]))
  }
}

resource "oci_vault_secret" "adb_wallet_password" {
  compartment_id = var.compartment_id
  secret_name    = "${var.name_prefix}-adb-wallet-password"
  description    = "Password used to open the CIS Autonomous Database wallet"
  vault_id       = oci_kms_vault.cis.id
  key_id         = oci_kms_key.cis.id

  secret_content {
    content_type = "BASE64"
    content      = base64encode(random_password.adb_wallet.result)
  }
}
