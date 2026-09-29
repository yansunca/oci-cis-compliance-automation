# CIS scanner upgrade: CI/CD instructions

Run all commands from the repository root. Replace `<placeholders>` with your values.
Your CI/CD runner needs Python 3.9+, Docker authenticated to OCIR, and an authenticated
OCI CLI with permission to read/update the controller Function. It must be able to
pull/push the runner image and build for the deployed runner's CPU architecture.
Allow network access to GitHub, OCIR, and OCI APIs. Configure credentials through
your CI/CD secret store and use the same OCI identity/profile throughout the job.
Set `<function-ocid>` from the deployment's `controller_function_id` output and
`<region>` from its `region` output, or obtain both from the controller's OCI Console
page. Terraform is not required on the upgrade runner.

These scripts replace `cis_reports.py` and its version label in the runner image,
then update `CIS_RUNNER_IMAGE`. Dependencies, the controller image, and scan schedule
remain unchanged. Scanner release numbers are not CIS benchmark versions: confirm
that the selected upstream release supports your required benchmark. Before your
first production upgrade, complete an upgrade, scan, and rollback in a non-production
environment. Confirm compatibility with the dependencies retained in the image.

## CI/CD setup

Configure these once in your CI/CD platform:

| Pipeline responsibility | Required setup |
| --- | --- |
| Trigger and execution | Choose a schedule or manual trigger; allow only one deployment per Function at a time. Stop on nonzero command exit codes. |
| Version decision | Implement the comparison in step 2; save the checker JSON for comparison after the build. |
| Artifacts | Store records by Function OCID, region, and pipeline run ID. Restore them in subsequent jobs; use the run ID in the build output directory. Persist the generated tfvars file for future Terraform jobs. |
| Scan validation | Connect your scan trigger and run-specific Object Storage/ADB checks in step 5. Set a timeout and fail the job if validation fails. Promote the baseline only after validation succeeds. |

The scripts do not implement these pipeline steps or automatically roll back a
failed scan. Configure the rollback command below as a recovery job. Complete the
non-production workflow before enabling scheduled production upgrades.

## 1. Read the deployed image

```text
oci fn function get --function-id <function-ocid> --region <region> --query data.config.CIS_RUNNER_IMAGE --raw-output
```

Use the result as `<current-image>`. Use the controller Function OCID, not a
Container Instance OCID. Retain its last successfully deployed and scan-verified
`upgrade.json` as the version baseline; its `new_image` must match the live digest.
If the live value is a tag, resolve its actual registry digest before comparing.

## 2. Check whether an upgrade is needed

```text
python3 scripts/check_latest_cis_release.py
```

Your pipeline compares the checker's `latestTag` and `scriptSha256` with the
baseline's `cis_version` and `script_sha256`. Ignore an optional leading `v` and
compare version numbers numerically.

| Comparison | Action |
| --- | --- |
| Same version and checksum | Skip the upgrade. |
| Newer stable version | Use `latestTag` as `<release-tag>` below. |
| Same version, different checksum; older release; lookup failure; missing or mismatched baseline | Stop for review. |

The checker only reads upstream metadata; it does not compare against deployment.
**Your CI/CD pipeline must implement this comparison.** Exit code zero means the
lookup succeeded, not that an upgrade is available. On the first run, establish
the deployed version/checksum or approve an initial upgrade and save its baseline
after scan verification. For a manually approved release, this lookup is optional;
record the approved release tag and source checksum for the build verification.

## 3. Build and publish

Use these values in the build command:

| Placeholder | Where to get the value |
| --- | --- |
| `<current-image>` | Copy the `CIS_RUNNER_IMAGE` value returned by the OCI CLI command in step 1. |
| `<release-tag>` | Copy `latestTag` from the release checker output in step 2, or use the specific release tag approved for a manual upgrade. |
| `<output-directory>` | Choose a new directory that does not already exist, such as `build/cis-upgrade-001`. The script creates it and saves `upgrade.json` there. |

```text
python3 scripts/cis-scanner-upgrade/upgrade_cis_scanner.py --current-image <current-image> --version <release-tag> --output <output-directory>
```

Use a new output directory for each build. This step publishes a new image without
updating production. It runs an offline import/checksum check using the retained
dependencies. Before deploying, compare the generated `upgrade.json` fields
`cis_version` and `script_sha256` with the saved checker results (or the manually
approved tag/checksum); stop if they differ. Normalize an optional `v` in the version.
Save `upgrade.json` as a CI/CD artifact. Retain both images identified by
`new_image` and `previous_image` in OCIR for rollback.

## 4. Update the controller

Preview the change:

```text
python3 scripts/cis-scanner-upgrade/update_cis_scanner_config.py upgrade --record <output-directory>/upgrade.json --function-id <function-ocid> --region <region>
```

Restore the build's `upgrade.json` if deployment runs in a separate job, then apply:

```text
python3 scripts/cis-scanner-upgrade/update_cis_scanner_config.py upgrade --record <output-directory>/upgrade.json --function-id <function-ocid> --region <region> --apply
```

Add `--profile <profile>` if required.
The updater preserves other Function configuration, checks for concurrent changes,
and verifies the configured image URI. Run only one upgrade or infrastructure
deployment at a time for this Function. Stop the pipeline if any command fails.

After a verified update, it generates `<output-directory>/cis-scanner.auto.tfvars`.
**Copy this file beside `main.tf` in the repository root used for Terraform deployments.**
Keep the latest copy in every future deployment checkout; leave `terraform.tfvars`
unchanged. Check for overriding `-var`, `-var-file`, platform variables, or
later-sorting auto.tfvars files. Generate a fresh Terraform plan and confirm it
retains the selected image; discard saved plans containing the old image.
These scripts do not run Terraform.

## 5. Validate and retain the baseline

Trigger a scan through your normal process. Verify `_SUCCESS`, `run_ready.json`,
and successful ADB/APEX ingestion for the run. Only then retain this `upgrade.json`
as the deployed baseline for this Function/region. Keep previous records for rollback.

## Rollback

Use the record from the upgrade being reverted:

```text
python3 scripts/cis-scanner-upgrade/update_cis_scanner_config.py rollback --record <output-directory>/upgrade.json --function-id <function-ocid> --region <region> --apply
```

Rollback selects `previous_image` for subsequent scans and regenerates
`cis-scanner.auto.tfvars`; copy it beside `main.tf` again. Verify a scan, then restore
the older baseline whose `new_image` matches the restored digest. The reverted
record's `cis_version` describes the rejected image, not the restored image.
Pause automatic upgrades to the rejected release until it is approved for retry.

## Troubleshooting

| Issue | Action |
| --- | --- |
| Image build or import check fails | Check the build output and scanner dependency requirements. Resolve the error and retry with a new output directory. |
| Configuration update fails or times out | Repeat step 1 to check the live image before retrying; the update may already have completed. |
| `cis-scanner.auto.tfvars` cannot be written | Correct the output path or permissions, then rerun the same update command with `--apply`. |
| Scan or ingestion fails after upgrade | Check the scan logs and report compatibility. Use the rollback command if you need to restore the previous scanner. |
