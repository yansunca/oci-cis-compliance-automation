#!/usr/bin/env bash
set -euo pipefail

SQL_BIN="${SQL_BIN:-sql}"
ADB_DEPLOY_OUTPUT_DIR="${ADB_DEPLOY_OUTPUT_DIR:-./build/adb-deploy}"
ADB_WALLET_ZIP="${ADB_WALLET_ZIP:-}"
ADB_CONNECT_ALIAS="${ADB_CONNECT_ALIAS:-cisautomation_low}"
ADB_USER="${ADB_USER:-ADMIN}"
ADB_PASSWORD="${ADB_PASSWORD:-}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"
IMPORT_APEX="${IMPORT_APEX:-true}"
APEX_WORKSPACE="${APEX_WORKSPACE:-OCI_CIS_FINDINGS}"
APEX_APP_SCHEMA="${APEX_APP_SCHEMA:-OCI_CIS_APP}"
APEX_APP_SCHEMA_PASSWORD="${APEX_APP_SCHEMA_PASSWORD:-}"
CREATE_APEX_SCHEMA="${CREATE_APEX_SCHEMA:-true}"
CREATE_APEX_WORKSPACE="${CREATE_APEX_WORKSPACE:-true}"
APEX_APP_ID="${APEX_APP_ID:-100}"
APEX_APP_ALIAS="${APEX_APP_ALIAS:-OCI-CIS-FINDINGS-OPERATIONS}"
APEX_APP_NAME="${APEX_APP_NAME:-OCI CIS Findings Operations}"
APEX_EXPORT_FILE="${APEX_EXPORT_FILE:-apex/export/f100_oci_cis_findings_operations_demo.sql}"
APEX_WORKSPACE_SETUP_SQL="${APEX_WORKSPACE_SETUP_SQL:-}"
APEX_BASE_URL="${APEX_BASE_URL:-}"

usage() {
  cat <<'USAGE'
Deploy ADB schema migrations and import the APEX CIS Findings Operations app.

Required environment:
  ADB_WALLET_ZIP=/path/to/Wallet_<ADB>.zip
  ADB_PASSWORD=<ADMIN password or target DB user password>

Common optional environment:
  ADB_CONNECT_ALIAS=cisautomation_low
  ADB_USER=ADMIN
  APEX_WORKSPACE=OCI_CIS_FINDINGS
  APEX_APP_SCHEMA=OCI_CIS_APP
  APEX_APP_SCHEMA_PASSWORD=<optional parsing schema password>
  CREATE_APEX_SCHEMA=true
  CREATE_APEX_WORKSPACE=true
  APEX_APP_ID=100
  APEX_APP_ALIAS=OCI-CIS-FINDINGS-OPERATIONS
  APEX_WORKSPACE_SETUP_SQL=/path/to/customer-approved-workspace-setup.sql
  APEX_BASE_URL=https://<adb-hostname>.oraclecloudapps.com

Examples:
  ADB_WALLET_ZIP=/secure/Wallet_CISAUTOMATION.zip \
  ADB_PASSWORD='<password>' \
  APEX_WORKSPACE=OCI_CIS_FINDINGS \
  scripts/deploy_adb_apex.sh

  RUN_MIGRATIONS=false IMPORT_APEX=true scripts/deploy_adb_apex.sh
USAGE
}

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  usage
  exit 0
fi

if ! command -v "$SQL_BIN" >/dev/null 2>&1; then
  echo "ERROR: SQLcl command '$SQL_BIN' was not found. Install SQLcl or set SQL_BIN=/path/to/sql." >&2
  exit 2
fi

if [ -z "$ADB_WALLET_ZIP" ] || [ ! -f "$ADB_WALLET_ZIP" ]; then
  echo "ERROR: ADB_WALLET_ZIP must point to an existing ADB wallet zip." >&2
  exit 2
fi

if [ -z "$ADB_PASSWORD" ]; then
  printf 'ADB password for %s: ' "$ADB_USER" >&2
  stty -echo
  IFS= read -r ADB_PASSWORD
  stty echo
  printf '\n' >&2
fi

case "$ADB_PASSWORD" in
  *$'\n'*|*'"'*)
    echo 'ERROR: ADB_PASSWORD must not contain a newline or double quote for this non-interactive SQLcl wrapper.' >&2
    exit 2
    ;;
esac

case "$APEX_APP_SCHEMA" in
  *[!A-Za-z0-9_]*|'')
    echo 'ERROR: APEX_APP_SCHEMA must contain only letters, numbers, and underscores.' >&2
    exit 2
    ;;
esac

case "$APEX_WORKSPACE" in
  *[!A-Za-z0-9_]*|'')
    echo 'ERROR: APEX_WORKSPACE must contain only letters, numbers, and underscores.' >&2
    exit 2
    ;;
esac

if [ ! -f "$APEX_EXPORT_FILE" ]; then
  echo "ERROR: APEX export file not found: $APEX_EXPORT_FILE" >&2
  exit 2
fi

mkdir -p "$ADB_DEPLOY_OUTPUT_DIR"
python3 scripts/build_adb_deploy_package.py --output-dir "$ADB_DEPLOY_OUTPUT_DIR" >/dev/null

work_dir="$(mktemp -d "${TMPDIR:-/tmp}/oci-cis-adb-apex.XXXXXX")"
chmod 700 "$work_dir"
cleanup() {
  rm -rf "$work_dir"
}
trap cleanup EXIT

run_sql_driver() {
  local driver="$1"
  local label="$2"
  local output="$work_dir/${label}.out"

  set +e
  "$SQL_BIN" -L -cloudconfig "$ADB_WALLET_ZIP" -s /nolog @"$driver" >"$output" 2>&1
  local sql_status=$?
  set -e

  cat "$output"

  if [ "$sql_status" -ne 0 ] || grep -Eq 'Connection Failed|Error report|ORA-[0-9]{5}|SP2-[0-9]{4}|PLS-[0-9]{5}' "$output"; then
    echo "ERROR: SQLcl step '${label}' failed. See output above." >&2
    exit 1
  fi
}

run_sql_file() {
  local db_user="${1:-$ADB_USER}"
  local db_password="${2:-$ADB_PASSWORD}"
  local sql_file="$3"
  local label="$4"
  local driver="$work_dir/${label}.sql"
  cat >"$driver" <<SQL
set define off
set sqlblanklines on
whenever sqlerror exit sql.sqlcode rollback
connect ${db_user}/"${db_password}"@${ADB_CONNECT_ALIAS}
@${sql_file}
exit success
SQL
  chmod 600 "$driver"
  run_sql_driver "$driver" "$label"
}

run_sql_inline() {
  local db_user="${1:-$ADB_USER}"
  local db_password="${2:-$ADB_PASSWORD}"
  local sql_body="$3"
  local label="$4"
  local driver="$work_dir/${label}.sql"
  cat >"$driver" <<SQL
set define off
set sqlblanklines on
whenever sqlerror exit sql.sqlcode rollback
connect ${db_user}/"${db_password}"@${ADB_CONNECT_ALIAS}
${sql_body}
exit success
SQL
  chmod 600 "$driver"
  run_sql_driver "$driver" "$label"
}

if [ "$CREATE_APEX_SCHEMA" = "true" ]; then
  echo "Creating or verifying APEX parsing schema ${APEX_APP_SCHEMA}..."
  if [ -z "$APEX_APP_SCHEMA_PASSWORD" ]; then
    APEX_APP_SCHEMA_PASSWORD="OciCisAppA1x$(date +%s)"
  fi
  run_sql_inline "$ADB_USER" "$ADB_PASSWORD" "
declare
  l_count number;
begin
  select count(*)
    into l_count
    from dba_users
   where username = upper('${APEX_APP_SCHEMA}');

  if l_count = 0 then
    execute immediate 'create user ${APEX_APP_SCHEMA} identified by "${APEX_APP_SCHEMA_PASSWORD}"';
  else
    execute immediate 'alter user ${APEX_APP_SCHEMA} account unlock identified by "${APEX_APP_SCHEMA_PASSWORD}"';
  end if;
end;
/
grant create session, create table, create view, create sequence, create procedure, create trigger, create type to ${APEX_APP_SCHEMA};
alter user ${APEX_APP_SCHEMA} quota unlimited on data;
" "apex_schema"
else
  echo "Skipping APEX parsing schema setup because CREATE_APEX_SCHEMA=$CREATE_APEX_SCHEMA"
  if [ "$RUN_MIGRATIONS" = "true" ] && [ -z "$APEX_APP_SCHEMA_PASSWORD" ]; then
    echo "ERROR: APEX_APP_SCHEMA_PASSWORD is required when RUN_MIGRATIONS=true and CREATE_APEX_SCHEMA=false." >&2
    exit 2
  fi
fi

if [ "$CREATE_APEX_WORKSPACE" = "true" ]; then
  echo "Creating or verifying APEX workspace ${APEX_WORKSPACE}..."
  run_sql_inline "$ADB_USER" "$ADB_PASSWORD" "
declare
  l_count number;
begin
  select count(*)
    into l_count
    from apex_workspaces
   where workspace = upper('${APEX_WORKSPACE}');

  if l_count = 0 then
    apex_instance_admin.add_workspace(
      p_workspace      => upper('${APEX_WORKSPACE}'),
      p_primary_schema => upper('${APEX_APP_SCHEMA}')
    );
  else
    apex_instance_admin.add_schema(
      p_workspace => upper('${APEX_WORKSPACE}'),
      p_schema    => upper('${APEX_APP_SCHEMA}')
    );
  end if;
  commit;
exception
  when others then
    if sqlcode in (-1, -20001, -20987) then
      null;
    else
      raise;
    end if;
end;
/
" "apex_workspace"
else
  echo "Skipping APEX workspace setup because CREATE_APEX_WORKSPACE=$CREATE_APEX_WORKSPACE"
fi

if [ -n "$APEX_WORKSPACE_SETUP_SQL" ]; then
  if [ ! -f "$APEX_WORKSPACE_SETUP_SQL" ]; then
    echo "ERROR: APEX_WORKSPACE_SETUP_SQL not found: $APEX_WORKSPACE_SETUP_SQL" >&2
    exit 2
  fi
  echo "Running customer-provided APEX workspace setup SQL..."
  run_sql_file "$ADB_USER" "$ADB_PASSWORD" "$APEX_WORKSPACE_SETUP_SQL" "workspace_setup"
fi

if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "Running ADB migration bundle as ${APEX_APP_SCHEMA}..."
  run_sql_file "$APEX_APP_SCHEMA" "$APEX_APP_SCHEMA_PASSWORD" "$ADB_DEPLOY_OUTPUT_DIR/phase3_adb_migration_bundle.sql" "migrations"
else
  echo "Skipping ADB migrations because RUN_MIGRATIONS=$RUN_MIGRATIONS"
fi

if [ "$IMPORT_APEX" = "true" ]; then
  echo "Importing APEX application..."
  import_driver="$work_dir/import_apex.sql"
  cat >"$import_driver" <<SQL
set define off
set sqlblanklines on
whenever sqlerror exit sql.sqlcode rollback
connect ${ADB_USER}/"${ADB_PASSWORD}"@${ADB_CONNECT_ALIAS}
begin
  apex_application_install.set_workspace('${APEX_WORKSPACE}');
  apex_application_install.set_application_id(${APEX_APP_ID});
  apex_application_install.set_application_alias('${APEX_APP_ALIAS}');
  apex_application_install.set_application_name('${APEX_APP_NAME}');
  apex_application_install.set_schema('${APEX_APP_SCHEMA}');
end;
/
@${APEX_EXPORT_FILE}
exit success
SQL
  chmod 600 "$import_driver"
  run_sql_driver "$import_driver" "import_apex"
else
  echo "Skipping APEX import because IMPORT_APEX=$IMPORT_APEX"
fi

if [ "$CREATE_APEX_SCHEMA" = "true" ]; then
  echo "Locking APEX parsing schema ${APEX_APP_SCHEMA}..."
  run_sql_inline "$ADB_USER" "$ADB_PASSWORD" "
alter user ${APEX_APP_SCHEMA} account lock;
" "lock_apex_schema"
fi

workspace_path="$(printf '%s' "$APEX_WORKSPACE" | tr '[:upper:]' '[:lower:]')"
app_path="$(printf '%s' "$APEX_APP_ALIAS" | tr '[:upper:]' '[:lower:]')"

cat <<MSG

ADB/APEX deployment steps completed.
Workspace: ${APEX_WORKSPACE}
Application alias: ${APEX_APP_ALIAS}
Application path: /ords/r/${workspace_path}/${app_path}/
MSG

if [ -n "$APEX_BASE_URL" ]; then
  echo "APEX URL: ${APEX_BASE_URL%/}/ords/r/${workspace_path}/${app_path}/"
else
  echo "Set APEX_BASE_URL=https://<adb-hostname> to print the full APEX URL."
fi
