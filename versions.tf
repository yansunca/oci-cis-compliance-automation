terraform {
  required_version = ">= 1.5.7"

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = "~> 8.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.7"
    }
  }
}

provider "oci" {
  region = var.region
}
