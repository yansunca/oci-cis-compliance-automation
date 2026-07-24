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

To refresh the export after approved APEX Builder edits:

1. Confirm the app uses only the approved `V_CIS_*` and `VW_*` views.
2. Apply required overlays after importing or rebuilding the app:

```bash
sql ADMIN/<password>@cisfindatp_low @page10-work-queue-drill-overlay.sql
sql ADMIN/<password>@cisfindatp_low @page20-finding-detail-overlay.sql
```

3. Run from this directory:

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
- Page 10 overlay also defines a public `High Priority` saved report; verify it in live metadata
  after applying the overlay because APEX application export may omit non-default public report
  variants.
- Page 20 detail is SQL-backed and filtered by `P20_FINDING_ID`.
