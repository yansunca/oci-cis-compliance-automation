# APEX Export Package

This directory contains the source-controlled APEX export workflow for the OCI CIS Findings
Operations demo.

## Live ADB Probe

The live ADB exposes APEX packages through `APEX_240200` and public synonyms:

- `APEX_APPLICATION_INSTALL`
- `APEX_EXPORT`
- `APEX_UTIL`

`APEX_WORKSPACES` is present. The workspace columns include `WORKSPACE`, `WORKSPACE_ID`, and
`SCHEMAS`.

## Export Workflow

The live demo export has been captured from:

- Workspace: `OCI_CIS_FINDINGS`
- Application: `100` / `OCI CIS Findings Operations`
- Parsing schema: `OCI_CIS_APP`
- Export: [`f100_oci_cis_findings_operations_demo.sql`](f100_oci_cis_findings_operations_demo.sql)
- Metadata: [`f100_oci_cis_findings_operations_demo.metadata.json`](f100_oci_cis_findings_operations_demo.metadata.json)
- Page 10 Work Queue drill-link overlay:
  [`page10-work-queue-drill-overlay.sql`](page10-work-queue-drill-overlay.sql)
- Page 20 read-only Finding Detail overlay:
  [`page20-finding-detail-overlay.sql`](page20-finding-detail-overlay.sql)
- Page 50 Scan Runs artifact-count overlay:
  [`page50-scan-runs-artifact-counts-overlay.sql`](page50-scan-runs-artifact-counts-overlay.sql)

Normal deployments should use [`../../scripts/deploy_adb_apex.sh`](../../scripts/deploy_adb_apex.sh). That script imports the base application and applies the required page overlays automatically.

To refresh the export after approved APEX Builder edits:

1. Confirm the app uses only the approved `OCI_CIS_APP.V_CIS_*` and `OCI_CIS_APP.VW_*` views.
2. Run from this directory:

```bash
sql ADMIN/<password>@cisfindatp_low @export_apex_app.sql OCI_CIS_FINDINGS 100
```

The script calls `APEX_EXPORT.GET_APPLICATION` and writes
`f<application_id>_oci_cis_findings_operations_demo.sql`.

## Boundary

- This package does not include passwords, wallet paths, or workspace-specific exports.
- Do not commit exports that contain environment-specific credentials, authorization schemes, or
  public Object Storage URLs.
- The current demo is read-only. Assignment, comments, risk acceptance, suppression, action audit,
  and workflow authorization schemes are intentionally not part of the active APEX package.
- Page 10 default report is `Open Work`, with priority/risk/age sorting and row highlights for
  high-priority and overdue findings.
- Page 10 overlay defines the Work Queue drill link into Page 20.
- Page 20 overlay exposes CIS recommendation details, native report links, and best-evidence download links.
- Page 50 overlay exposes native report file counts and indexed artifact counts.
- Page 20 detail is SQL-backed and filtered by `P20_FINDING_ID`.
