#!/usr/bin/env bash
set -euo pipefail

TF_BIN="${TF_BIN:-terraform}"
if ! command -v "$TF_BIN" >/dev/null 2>&1; then
  if command -v tofu >/dev/null 2>&1; then
    TF_BIN=tofu
  else
    echo "ERROR: terraform or tofu is required" >&2
    exit 2
  fi
fi

: "${REGION_KEY:?Set REGION_KEY, for example iad}"
: "${TENANCY_NAMESPACE:?Set TENANCY_NAMESPACE, your Object Storage/OCIR namespace}"
: "${NAME_PREFIX:=cis-auto}"
: "${TAG:=v1}"
: "${APPLY:=false}"
: "${BOOTSTRAP_REPOS:=false}"
: "${PUSH_IMAGES:=false}"

if [ ! -f terraform.tfvars ]; then
  echo "ERROR: terraform.tfvars is missing. Copy terraform.tfvars.example and fill in tenancy values." >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required to build/push images" >&2
  exit 2
fi

$TF_BIN init

if [ "$BOOTSTRAP_REPOS" = "true" ]; then
  $TF_BIN apply \
    -target=oci_artifacts_container_repository.controller \
    -target=oci_artifacts_container_repository.runner \
    -target=oci_artifacts_container_repository.object_event_loader \
    -target=oci_artifacts_container_repository.adb_sql_loader
fi

if [ "$PUSH_IMAGES" = "true" ]; then
  make push REGION_KEY="$REGION_KEY" TENANCY_NAMESPACE="$TENANCY_NAMESPACE" NAME_PREFIX="$NAME_PREFIX" TAG="$TAG"
else
  echo "Skipping image build/push. Set PUSH_IMAGES=true after OCIR repositories exist."
fi

if [ "$APPLY" = "true" ]; then
  $TF_BIN apply
else
  $TF_BIN plan
  echo "Set APPLY=true to run the full terraform apply after reviewing the plan."
fi

python3 scripts/build_adb_deploy_package.py --output-dir ./build/adb-deploy
cat <<MSG

ADB/APEX bundle generated under ./build/adb-deploy.
Import apex/export/f100_oci_cis_findings_operations_demo.sql after running the SQL bundle/migrations.
MSG
