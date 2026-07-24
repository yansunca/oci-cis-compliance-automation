-- Optimize scan-run health reporting for dashboard consumers.
--
-- The original view joined every per-run child table at once and then de-duplicated
-- after the join. Once a demo run has enough files, raw rows, stage rows, and
-- observations, that creates a large cross-product before aggregation.
-- Pre-aggregate each child table at run grain and join the small rollups.

CREATE OR REPLACE VIEW vw_scan_run_health AS
WITH file_rollup AS (
    SELECT
        run_id,
        COUNT(*) AS file_count,
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
