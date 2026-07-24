# Database Migrations

Use ordered filenames such as `V0001__create_scan_tables.sql`.

Current highest migration: `V0022__remove_demo_workflow_objects.sql`.

`V0022` removes retired workflow/action objects from existing demo databases and rebuilds Finding
Detail as a read-only CIS audit/evidence view. It leaves scan runs, raw CIS records, canonical
findings, product mappings, and report artifact links intact.
