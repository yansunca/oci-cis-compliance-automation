-- Clarify scan-run artifact counts for APEX/OAC audit views.
--
-- `file_count` historically meant every indexed artifact in scan_file, including
-- both native CIS report files and app-generated JSONL audit/load artifacts.
-- Keep that column for compatibility and expose explicit native/app counts so
-- operators do not compare it directly to Function run_ready.reportFileCount.

CREATE OR REPLACE VIEW vw_scan_run_health AS
WITH file_rollup AS (
    SELECT
        run_id,
        COUNT(*) AS file_count,
        COUNT(*) AS indexed_artifact_count,
        SUM(CASE WHEN file_format <> 'JSONL' THEN 1 ELSE 0 END)
            AS native_report_file_count,
        SUM(CASE WHEN file_format = 'JSONL' THEN 1 ELSE 0 END)
            AS app_audit_artifact_count,
        SUM(CASE WHEN required_for_completeness = 'Y' THEN 1 ELSE 0 END)
            AS required_file_count,
        MIN(created_at) AS first_file_loaded_at
    FROM scan_file
    GROUP BY run_id
),
raw_rollup AS (
    SELECT
        run_id,
        COUNT(*) AS raw_record_count
    FROM raw_cis_record
    GROUP BY run_id
),
stage_rollup AS (
    SELECT
        run_id,
        COUNT(*) AS canonical_stage_count
    FROM canonical_finding_stage
    GROUP BY run_id
),
observation_rollup AS (
    SELECT
        run_id,
        COUNT(*) AS observation_count,
        MAX(created_at) AS last_observation_loaded_at
    FROM finding_observation
    GROUP BY run_id
)
SELECT
    run.run_id,
    run.tenancy_id,
    run.status,
    run.started_at,
    run.completed_at,
    run.scanner_version,
    run.scanner_commit,
    run.wrapper_version,
    run.benchmark_version,
    DBMS_LOB.SUBSTR(run.requested_regions_json, 4000, 1) AS requested_regions_json,
    DBMS_LOB.SUBSTR(run.completed_regions_json, 4000, 1) AS completed_regions_json,
    run.manifest_checksum,
    COALESCE(file_rollup.file_count, 0) AS file_count,
    COALESCE(file_rollup.indexed_artifact_count, 0) AS indexed_artifact_count,
    COALESCE(file_rollup.native_report_file_count, 0) AS native_report_file_count,
    COALESCE(file_rollup.app_audit_artifact_count, 0) AS app_audit_artifact_count,
    COALESCE(raw_rollup.raw_record_count, 0) AS raw_record_count,
    COALESCE(stage_rollup.canonical_stage_count, 0) AS canonical_stage_count,
    COALESCE(observation_rollup.observation_count, 0) AS observation_count,
    COALESCE(file_rollup.required_file_count, 0) AS required_file_count,
    file_rollup.first_file_loaded_at,
    observation_rollup.last_observation_loaded_at
FROM scan_run run
LEFT JOIN file_rollup
    ON file_rollup.run_id = run.run_id
LEFT JOIN raw_rollup
    ON raw_rollup.run_id = run.run_id
LEFT JOIN stage_rollup
    ON stage_rollup.run_id = run.run_id
LEFT JOIN observation_rollup
    ON observation_rollup.run_id = run.run_id;

CREATE OR REPLACE VIEW v_cis_scan_summary AS
SELECT
    run_id,
    tenancy_id,
    status,
    started_at,
    completed_at,
    scanner_version,
    benchmark_version,
    file_count,
    indexed_artifact_count,
    native_report_file_count,
    app_audit_artifact_count,
    raw_record_count,
    canonical_stage_count,
    observation_count
FROM vw_scan_run_health;

GRANT SELECT ON vw_scan_run_health TO oci_cis_app;
GRANT SELECT ON v_cis_scan_summary TO oci_cis_app;
