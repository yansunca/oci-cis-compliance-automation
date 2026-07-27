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
: "${SKIP_INIT:=false}"

if [ ! -f terraform.tfvars ]; then
  echo "ERROR: terraform.tfvars is missing. Copy terraform.tfvars.example and fill in tenancy values." >&2
  exit 2
fi

if [ "$PUSH_IMAGES" = "true" ]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker is required when PUSH_IMAGES=true" >&2
    exit 2
  fi
  host_arch="$(uname -m)"
  needs_amd64="${CONTROLLER_PLATFORM:-linux/amd64} ${RUNNER_PLATFORM:-linux/amd64} ${LOADER_PLATFORM:-linux/amd64}"
  if [ "$host_arch" = "arm64" ] && printf '%s' "$needs_amd64" | grep -q 'linux/amd64'; then
    if ! docker buildx version >/dev/null 2>&1; then
      cat >&2 <<'ERR'
ERROR: This deployment builds linux/amd64 images, but this host is arm64 and Docker Buildx is not available.

Use one of these options:
  1. Run the image build/push from an AMD/x86 builder, such as OCI Cloud Shell or an AMD Linux VM.
  2. Install/enable Docker Buildx locally.
  3. Switch the scanner to A1 ARM only if all deployed image targets support ARM.

No Terraform apply was run by this script before this check.
ERR
      exit 2
    fi
  fi
fi

if [ "$SKIP_INIT" = "true" ]; then
  echo "Skipping terraform init because SKIP_INIT=true."
else
  $TF_BIN init
fi

if [ "$BOOTSTRAP_REPOS" = "true" ]; then
  $TF_BIN apply \
    -target=oci_artifacts_container_repository.controller \
    -target=oci_artifacts_container_repository.runner \
    -target=oci_artifacts_container_repository.object_event_loader \
    -target=oci_artifacts_container_repository.adb_sql_loader
fi

if [ "$PUSH_IMAGES" = "true" ]; then
  DOCKER_BUILDKIT=1 make push REGION_KEY="$REGION_KEY" TENANCY_NAMESPACE="$TENANCY_NAMESPACE" NAME_PREFIX="$NAME_PREFIX" TAG="$TAG"
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
After Terraform creates ADB, run scripts/install_adb_apex_app.sh to install the SQL bundle and APEX app.
MSG
