#!/usr/bin/env bash
set -euo pipefail

TF_BIN="${TF_BIN:-terraform}"
if ! command -v "$TF_BIN" >/dev/null 2>&1; then
  if command -v tofu >/dev/null 2>&1; then
    TF_BIN=tofu
  else
    echo "ERROR: terraform or tofu is required to read stack outputs. Set ADB_ID explicitly to skip Terraform output lookup." >&2
    exit 2
  fi
fi

REGION="${REGION:-$(terraform output -raw region 2>/dev/null || true)}"
REGION="${REGION:-us-ashburn-1}"
ADB_ID="${ADB_ID:-$($TF_BIN output -raw autonomous_database_id 2>/dev/null || true)}"
ADB_NAME="${ADB_NAME:-CISAUTOMATION}"
ADB_CONNECT_ALIAS="${ADB_CONNECT_ALIAS:-cisautomation_low}"
ADB_WALLET_ZIP="${ADB_WALLET_ZIP:-build/wallet/Wallet_${ADB_NAME}.zip}"
ADB_PASSWORD="${ADB_PASSWORD:-}"
ADB_WALLET_PASSWORD="${ADB_WALLET_PASSWORD:-}"
SQL_BIN="${SQL_BIN:-}"
JAVA_HOME="${JAVA_HOME:-}"
APEX_WORKSPACE="${APEX_WORKSPACE:-OCI_CIS_FINDINGS}"
APEX_APP_SCHEMA="${APEX_APP_SCHEMA:-OCI_CIS_APP}"
APEX_USERNAME="${APEX_USERNAME:-}"
APEX_USER_PASSWORD="${APEX_USER_PASSWORD:-}"
APEX_USER_EMAIL="${APEX_USER_EMAIL:-}"
CREATE_APEX_USER="${CREATE_APEX_USER:-false}"

usage() {
  cat <<'USAGE'
Install the OCI CIS ADB schema and APEX app after Terraform creates ADB.
Run from the Terraform working directory, or set ADB_ID explicitly.

Required environment:
  ADB_PASSWORD=<ADB ADMIN password>
  ADB_WALLET_PASSWORD=<new wallet password>

Optional environment:
  REGION=<oci_region>                         default: Terraform output or us-ashburn-1
  ADB_ID=<autonomous_database_ocid>           default: terraform output autonomous_database_id
  ADB_CONNECT_ALIAS=cisautomation_low
  ADB_WALLET_ZIP=build/wallet/Wallet_CISAUTOMATION.zip
  SQL_BIN=/path/to/sql                        default: auto-detect sql/sqlcl Homebrew cask
  JAVA_HOME=/path/to/jdk                      default: auto-detect Homebrew OpenJDK 17
  CREATE_APEX_USER=true
  APEX_USERNAME=<initial_user>
  APEX_USER_PASSWORD=<initial_user_password>
  APEX_USER_EMAIL=<initial_user_email>

Example:
  read -s ADB_PASSWORD; export ADB_PASSWORD
  read -s ADB_WALLET_PASSWORD; export ADB_WALLET_PASSWORD
  CREATE_APEX_USER=true \
  APEX_USERNAME=admin@example.com \
  APEX_USER_EMAIL=admin@example.com \
  scripts/install_adb_apex_app.sh
USAGE
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

if [ -z "$ADB_PASSWORD" ]; then
  printf 'ADB ADMIN password: ' >&2
  stty -echo
  IFS= read -r ADB_PASSWORD
  stty echo
  printf '\n' >&2
fi

if [ -z "$ADB_WALLET_PASSWORD" ]; then
  printf 'New ADB wallet password: ' >&2
  stty -echo
  IFS= read -r ADB_WALLET_PASSWORD
  stty echo
  printf '\n' >&2
fi

if [ -z "$ADB_ID" ]; then
  echo "ERROR: ADB_ID is required. Run Terraform first or set ADB_ID=<autonomous_database_ocid>." >&2
  exit 2
fi

if [ -z "$SQL_BIN" ]; then
  if command -v sql >/dev/null 2>&1; then
    SQL_BIN="$(command -v sql)"
  else
    SQL_BIN="$(find /opt/homebrew/Caskroom/sqlcl /usr/local/Caskroom/sqlcl -path '*/sqlcl/bin/sql' -type f 2>/dev/null | sort | tail -1 || true)"
  fi
fi

if [ -z "$SQL_BIN" ] || [ ! -x "$SQL_BIN" ]; then
  echo "ERROR: SQLcl was not found. Install SQLcl or set SQL_BIN=/path/to/sql." >&2
  exit 2
fi

if [ -z "$JAVA_HOME" ]; then
  for candidate in \
    /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home \
    /usr/local/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home \
    /opt/homebrew/opt/openjdk/libexec/openjdk.jdk/Contents/Home \
    /usr/local/opt/openjdk/libexec/openjdk.jdk/Contents/Home; do
    if [ -x "$candidate/bin/java" ]; then
      JAVA_HOME="$candidate"
      break
    fi
  done
fi

if [ -z "$JAVA_HOME" ] || [ ! -x "$JAVA_HOME/bin/java" ]; then
  echo "ERROR: Java 11 or newer was not found. Install a JDK or set JAVA_HOME." >&2
  exit 2
fi

mkdir -p "$(dirname "$ADB_WALLET_ZIP")"
if [ ! -f "$ADB_WALLET_ZIP" ]; then
  echo "Generating ADB wallet at $ADB_WALLET_ZIP..."
  oci db autonomous-database generate-wallet \
    --autonomous-database-id "$ADB_ID" \
    --password "$ADB_WALLET_PASSWORD" \
    --file "$ADB_WALLET_ZIP" \
    --region "$REGION"
else
  echo "Using existing ADB wallet: $ADB_WALLET_ZIP"
fi

if [ "$CREATE_APEX_USER" = "true" ] && [ -n "$APEX_USERNAME" ] && [ -z "$APEX_USER_PASSWORD" ]; then
  printf 'Initial APEX user password for %s: ' "$APEX_USERNAME" >&2
  stty -echo
  IFS= read -r APEX_USER_PASSWORD
  stty echo
  printf '\n' >&2
fi

export JAVA_HOME SQL_BIN ADB_WALLET_ZIP ADB_PASSWORD ADB_CONNECT_ALIAS APEX_WORKSPACE APEX_APP_SCHEMA
export CREATE_APEX_USER APEX_USERNAME APEX_USER_PASSWORD APEX_USER_EMAIL

scripts/deploy_adb_apex.sh
