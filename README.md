# OCI CIS compliance automation

OCI CIS compliance automation is a reference implementation for running OCI CIS scans and operating on the resulting findings in Oracle Cloud Infrastructure.

It packages a Container Instance scanner, controller Function, Object Storage event loader, ADB SQL loader, Autonomous Database schema, Oracle APEX operations UI, Terraform deployment starter, and supporting automation scripts. The project is intended for OCI cloud engineering teams to evaluate CIS findings operations patterns and adapt them into a customer-specific proof of concept.

This repository is a proof-of-concept reference implementation for evaluation purposes. It is not an Oracle product and is not covered by Oracle support.

## CIS reporting workflow

```mermaid
flowchart LR
  S["OCI Resource Scheduler"] --> C["Controller Function
create run and prevent overlap"]
  C --> CI["OCI Container Instance
real CIS scanner"]
  CI --> O["Object Storage
<run_id>/files/*
<run_id>/run_ready.json
<run_id>/_SUCCESS"]
  O --> E["Object Storage create event"]
  E --> L["Object event loader Function
process completion marker only"]
  L --> SQL["ADB SQL loader Function
normalize native CIS files"]
  SQL --> A["Autonomous Database
canonical CIS findings model"]
  A --> UI["Oracle APEX CIS Findings Operations UI
scan runs, product views, finding detail, audit links"]
  UI --> O
```

The scanner runs Oracle's `cis_reports.py` from the [OCI Landing Zones CIS quickstart](https://github.com/oci-landing-zones/oci-cis-landingzone-quickstart), preserves the native CIS CSV/HTML/JSON report artifacts in Object Storage, and writes each completed scan run to Object Storage using this layout: `<run_id>/files/*`, `<run_id>/run_ready.json`, and `<run_id>/_SUCCESS`. The event and SQL loader Functions then normalize the completed run into the ADB canonical CIS findings model, enrich it for product/compartment operations, and keep links back to the original report files so APEX can support operational review and audit evidence from the same source run.

## Contents

- `container/` - Container Instance scanner image.
- `functions/controller/` - Function that creates one Container Instance per scan run.
- `functions/object-storage-event-loader/` - Function triggered by Object Storage create events; it only proceeds on `_SUCCESS` markers.
- `functions/adb-sql-loader/` - Function that loads a completed run into ADB.
- `database/migrations/` - Canonical schema, product mapping, audit views, and APEX support objects.
- `apex/export/` - APEX application export for CIS findings operations, including scan runs, product views, finding detail, and audit evidence links.
- `scripts/` - Build/load helpers, including the ADB deployment package builder.

## Automated deploy

Prerequisites: Terraform/OpenTofu compatible with Terraform `1.5.7+`, OCI CLI credentials, Docker or Podman for image builds, and SQLcl for the ADB/APEX install step.

Create `terraform.tfvars`, log in to OCIR for the target region, then run the deployment phases:

```sh
docker login <region-key>.ocir.io
```

Plan only:

```sh
REGION_KEY=<region-key> \
TENANCY_NAMESPACE=<object-storage-namespace> \
NAME_PREFIX=cis-auto \
TAG=v1 \
APPLY=false \
scripts/deploy_stack.sh
```

Create OCIR repositories:

```sh
REGION_KEY=<region-key> \
TENANCY_NAMESPACE=<object-storage-namespace> \
NAME_PREFIX=cis-auto \
TAG=v1 \
BOOTSTRAP_REPOS=true \
APPLY=false \
scripts/deploy_stack.sh
```

Build and push images:

```sh
REGION_KEY=<region-key> \
TENANCY_NAMESPACE=<object-storage-namespace> \
NAME_PREFIX=cis-auto \
TAG=v1 \
PUSH_IMAGES=true \
APPLY=false \
scripts/deploy_stack.sh
```

Deploy the stack after reviewing the plan:

```sh
REGION_KEY=<region-key> \
TENANCY_NAMESPACE=<object-storage-namespace> \
NAME_PREFIX=cis-auto \
TAG=v1 \
APPLY=true \
scripts/deploy_stack.sh
```

The default image platform is `linux/amd64` and the default scanner shape is `CI.Standard.E4.Flex`. Use a compatible builder for the selected platform. To use ARM/A1, set `container_shape = "CI.Standard.A1.Flex"` and build with `RUNNER_PLATFORM=linux/arm64`.

To check for a new stable upstream CIS script release in CI:

```sh
python3 scripts/check_latest_cis_release.py
```

## Network choices

Function networking, scanner networking, and ADB/APEX networking are configured separately:

- Functions deploy to `existing_private_subnet_id`.
- The scanner uses `scanner_subnet_id` when set, otherwise the Function subnet.
- Set `assign_public_ip` according to the approved scanner subnet egress design.
- Set `adb_private_endpoint_subnet_id` to deploy ADB/APEX with private endpoint access.

For GovCloud or customer-controlled environments, use the customer's approved network, IAM, and data-access standards for the deployment compartment and tenancy read permissions required by the CIS benchmark.

## Private ADB/APEX access

When `adb_private_endpoint_subnet_id` is set, ADB SQL access and the APEX URL are private. Customer IT security and network teams should define the approved access path before the ADB/APEX install.

If OCI DNS Resolver support is required, this repository can create an inbound resolver endpoint:

```hcl
create_dns_resolver_inbound_endpoint = true
dns_resolver_endpoint_subnet_id      = "<subnet_reachable_from_customer_dns_or_vpn>"
dns_resolver_endpoint_nsg_id         = "<dns_resolver_nsg_ocid>"
dns_resolver_allowed_cidrs           = ["<customer_dns_or_vpn_cidr>"]
```

After apply, provide this output to the customer networking team if they use conditional DNS forwarding:

```sh
terraform output dns_resolver_inbound_endpoint_ip
```

## ADB and APEX installation

Terraform creates ADB, Function configuration, IAM, Object Storage, and related runtime resources. The database schema and APEX application are installed after ADB is available.

Required tools for this step: SQLcl, Java 11 or newer, the ADB wallet zip, and an execution host that can reach the ADB endpoint.

Generate a wallet using a new wallet password:

```sh
oci db autonomous-database generate-wallet \
  --autonomous-database-id $(terraform output -raw autonomous_database_id) \
  --password '<new_wallet_password>' \
  --file ~/Wallet_CISAUTOMATION.zip \
  --region <region>
```

Run the installer:

```sh
read -s ADB_PASSWORD
SQL_BIN=${SQL_BIN:-sql} \
ADB_WALLET_ZIP=~/Wallet_CISAUTOMATION.zip \
ADB_PASSWORD="$ADB_PASSWORD" \
ADB_CONNECT_ALIAS=cisautomation_low \
APEX_WORKSPACE=OCI_CIS_FINDINGS \
APEX_APP_SCHEMA=OCI_CIS_APP \
scripts/deploy_adb_apex.sh
```

The installer creates or verifies the `OCI_CIS_APP` parsing schema, creates or verifies the `OCI_CIS_FINDINGS` workspace, runs the ADB migration bundle, imports the APEX application, and prints the APEX path.

Default APEX values:

- Workspace: `OCI_CIS_FINDINGS`
- App ID: `100`
- App alias: `OCI-CIS-FINDINGS-OPERATIONS`
- Parsing schema: `OCI_CIS_APP`

APEX URL pattern:

```text
https://<adb-apex-hostname>/ords/r/OCI_CIS_FINDINGS/OCI-CIS-FINDINGS-OPERATIONS/home
```

For private ADB/APEX, use the ADB `connection-urls.apex-url` hostname, usually ending in `oraclecloudapps.com`, and preserve the exact APEX workspace path prefix case.

If APEX workspace creation is managed separately, set `CREATE_APEX_WORKSPACE=false`. If the parsing schema is also managed separately, set `CREATE_APEX_SCHEMA=false`.

## Product mapping tags

The APEX product views use the normalized CIS finding compartment plus configured product metadata. For the lowest-maintenance setup, tag product-owning compartments before running the scanner.

Recommended tag pattern:

```text
Tag namespace: Operations
Tag key: ProductId
Example value: OCI_POC
```

The loader snapshots compartment metadata from the CIS run and product enrichment resolves findings in this order:

1. Explicit product mapping override in ADB, when configured.
2. Product tag on the finding compartment or nearest tagged parent compartment.
3. Resource-level product tag, when present in the CIS source data.
4. Unmapped fallback for audit visibility.

A child compartment can override a parent product tag by setting its own `Operations.ProductId`. If no child tag exists, findings inherit the nearest tagged ancestor. After changing product tags, run a new scan so the next run captures the updated compartment/tag snapshot and APEX product scorecards reflect the change.

## Trigger a scan

Scheduled runs use OCI Resource Scheduler. For an on-demand run, invoke the controller Function:

```sh
export CONTROLLER_FUNCTION_ID=$(terraform output -raw controller_function_id)
export REGION=<region>
scripts/invoke_controller.sh

# Or invoke directly:
oci fn function invoke \
  --function-id <controller_function_ocid> \
  --body '{}' \
  --file /tmp/cis-controller-response.json \
  --region <region>
```

A successful scanner run writes these Object Storage objects:

```text
<run_id>/files/<native CIS report files>
<run_id>/run_ready.json
<run_id>/_SUCCESS
```

The Object Storage event loader receives create-object events for the bucket, ignores ordinary report files, and invokes the ADB SQL loader only when `_SUCCESS` or `_SUCCESS.txt` appears and `run_ready.json` exists.

## Security

This sample creates OCI IAM policies, Functions, Container Instances, Object Storage, and Autonomous Database resources. Review generated Terraform plans before applying them, scope compartments and dynamic groups for the customer environment, and rotate any setup passwords or auth tokens after deployment.

Do not commit wallet files, Terraform state files, API keys, OCIR auth tokens, or customer CIS report outputs.

## License

Copyright 2026 OCI CIS Compliance Automation contributors.

Licensed under the Apache License, Version 2.0. See [LICENSE.txt](LICENSE.txt).
