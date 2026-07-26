# Database Migrations

Use ordered filenames such as `V0001__create_scan_tables.sql`.

Current highest migration: `V0025__fix_admin_evidence_artifact_handler.sql`.

`V0022` removes retired workflow/action objects from existing demo databases and rebuilds Finding
Detail as a read-only CIS audit/evidence view. It leaves scan runs, raw CIS records, canonical
findings, product mappings, and report artifact links intact.

`V0023` through `V0025` keep the APEX dashboard, product scorecard, mapping quality, and evidence artifact download views aligned with the current app export.
