#!/usr/bin/env bash
set -euo pipefail

TF_BIN="${TF_BIN:-terraform}"
if ! command -v "$TF_BIN" >/dev/null 2>&1; then
  if command -v tofu >/dev/null 2>&1; then
    TF_BIN=tofu
  else
    TF_BIN=""
  fi
fi

REGION="${REGION:-}"
REGION_KEY="${REGION_KEY:-}"
TENANCY_NAMESPACE="${TENANCY_NAMESPACE:-}"
NAME_PREFIX="${NAME_PREFIX:-cis-auto}"
TAG="${TAG:-v1}"
COMPARTMENT_ID="${COMPARTMENT_ID:-}"

if [ -n "$TF_BIN" ]; then
  REGION="${REGION:-$($TF_BIN output -raw region 2>/dev/null || true)}"
  REGION_KEY="${REGION_KEY:-$($TF_BIN output -raw region_key 2>/dev/null || true)}"
  TENANCY_NAMESPACE="${TENANCY_NAMESPACE:-$($TF_BIN output -raw tenancy_namespace 2>/dev/null || true)}"
  COMPARTMENT_ID="${COMPARTMENT_ID:-$($TF_BIN output -raw compartment_id 2>/dev/null || true)}"
fi

: "${REGION:?Set REGION, for example us-ashburn-1}"
: "${REGION_KEY:?Set REGION_KEY, for example iad}"
: "${TENANCY_NAMESPACE:?Set TENANCY_NAMESPACE, your Object Storage/OCIR namespace}"
: "${COMPARTMENT_ID:?Set COMPARTMENT_ID, or run from a Terraform directory that outputs compartment_id}"

repository_name="${NAME_PREFIX}-runner"

digest="$(oci artifacts container image list \
  --compartment-id "$COMPARTMENT_ID" \
  --region "$REGION" \
  --all \
  --query "data.items[?\"repository-name\"==\`${repository_name}\` && version==\`${TAG}\`] | sort_by(@, &\"time-created\")[-1].digest" \
  --raw-output)"

if [ -z "$digest" ] || [ "$digest" = "null" ]; then
  echo "ERROR: no image found for ${repository_name}:${TAG} in compartment ${COMPARTMENT_ID}" >&2
  exit 2
fi

printf '%s.ocir.io/%s/%s@%s\n' "$REGION_KEY" "$TENANCY_NAMESPACE" "$repository_name" "$digest"
