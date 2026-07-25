locals {
  dns_resolver_endpoint_subnet_id = var.dns_resolver_endpoint_subnet_id == "" ? var.adb_private_endpoint_subnet_id : var.dns_resolver_endpoint_subnet_id
  dns_resolver_endpoint_enabled   = var.create_dns_resolver_inbound_endpoint && local.dns_resolver_endpoint_subnet_id != ""
  dns_resolver_nsg_rule_enabled   = local.dns_resolver_endpoint_enabled && var.dns_resolver_endpoint_nsg_id != ""
}

data "oci_core_subnet" "dns_resolver_endpoint" {
  count     = local.dns_resolver_endpoint_enabled ? 1 : 0
  subnet_id = local.dns_resolver_endpoint_subnet_id
}

data "oci_core_vcn_dns_resolver_association" "dns_resolver_endpoint" {
  count  = local.dns_resolver_endpoint_enabled ? 1 : 0
  vcn_id = data.oci_core_subnet.dns_resolver_endpoint[0].vcn_id
}

resource "oci_dns_resolver_endpoint" "private_adb_inbound" {
  count = local.dns_resolver_endpoint_enabled ? 1 : 0

  resolver_id       = data.oci_core_vcn_dns_resolver_association.dns_resolver_endpoint[0].dns_resolver_id
  name              = "${replace(var.name_prefix, "-", "_")}_adb_inbound"
  subnet_id         = local.dns_resolver_endpoint_subnet_id
  scope             = "PRIVATE"
  is_forwarding     = false
  is_listening      = true
  listening_address = var.dns_resolver_endpoint_listening_address == "" ? null : var.dns_resolver_endpoint_listening_address
  nsg_ids           = var.dns_resolver_endpoint_nsg_id == "" ? [] : [var.dns_resolver_endpoint_nsg_id]
  freeform_tags     = local.tags
}

resource "oci_core_network_security_group_security_rule" "dns_resolver_inbound_udp" {
  for_each = local.dns_resolver_nsg_rule_enabled ? toset(var.dns_resolver_allowed_cidrs) : []

  network_security_group_id = var.dns_resolver_endpoint_nsg_id
  direction                 = "INGRESS"
  protocol                  = "17"
  source                    = each.value
  source_type               = "CIDR_BLOCK"
  description               = "Allow DNS UDP/53 from customer VPN/corporate DNS to OCI inbound resolver"

  udp_options {
    destination_port_range {
      min = 53
      max = 53
    }
  }
}

resource "oci_core_network_security_group_security_rule" "dns_resolver_inbound_tcp" {
  for_each = local.dns_resolver_nsg_rule_enabled ? toset(var.dns_resolver_allowed_cidrs) : []

  network_security_group_id = var.dns_resolver_endpoint_nsg_id
  direction                 = "INGRESS"
  protocol                  = "6"
  source                    = each.value
  source_type               = "CIDR_BLOCK"
  description               = "Allow DNS TCP/53 from customer VPN/corporate DNS to OCI inbound resolver"

  tcp_options {
    destination_port_range {
      min = 53
      max = 53
    }
  }
}
