-- Initial reporting/workbench views for the OCI CIS POC.
-- These views expose stable read-side fields for APEX and analytics consumers.

CREATE OR REPLACE VIEW vw_finding_work_queue AS
SELECT
    finding.finding_id,
    finding.tenancy_id,
    finding.control_lineage_id,
    finding.control_display_id,
    finding.benchmark_version,
    finding.scope_type,
    finding.scope_key,
    finding.region,
    finding.current_state,
    finding.priority,
    finding.risk_score,
    finding.owner,
    finding.first_seen_at,
    finding.last_seen_at,
    finding.last_state_change_at,
    finding.resolved_at,
    finding.due_at,
    JSON_VALUE(finding.product_json, '$.productId' NULL ON ERROR) AS product_id,
    JSON_VALUE(finding.product_json, '$.displayName' NULL ON ERROR) AS product_display_name,
    JSON_VALUE(finding.product_json, '$.mappingSource' NULL ON ERROR) AS product_mapping_source,
    JSON_VALUE(finding.resource_json, '$.type' NULL ON ERROR) AS resource_type,
    JSON_VALUE(finding.resource_json, '$.name' NULL ON ERROR) AS resource_name,
    JSON_VALUE(finding.compartment_json, '$.ocid') AS compartment_ocid,
    JSON_VALUE(finding.compartment_json, '$.name') AS compartment_name,
    JSON_VALUE(finding.compartment_json, '$.path') AS compartment_path,
    latest_observation.run_id AS last_observed_run_id,
    latest_observation.source_file AS last_source_file,
    latest_observation.source_row AS last_source_row,
    latest_observation.schema_hash AS last_schema_hash,
    finding.updated_at
FROM canonical_finding finding
LEFT JOIN (
    SELECT
        observation.finding_id,
        observation.run_id,
        observation.source_file,
        observation.source_row,
        observation.schema_hash,
        ROW_NUMBER() OVER (
            PARTITION BY observation.finding_id
            ORDER BY observation.observed_at DESC, observation.observation_id DESC
        ) AS row_rank
    FROM finding_observation observation
) latest_observation
    ON latest_observation.finding_id = finding.finding_id
    AND latest_observation.row_rank = 1;

CREATE OR REPLACE VIEW vw_scan_run_health AS
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
    MAX(DBMS_LOB.SUBSTR(run.requested_regions_json, 4000, 1)) AS requested_regions_json,
    MAX(DBMS_LOB.SUBSTR(run.completed_regions_json, 4000, 1)) AS completed_regions_json,
    run.manifest_checksum,
    COUNT(DISTINCT scan_file.scan_file_id) AS file_count,
    COUNT(DISTINCT raw_record.raw_record_id) AS raw_record_count,
    COUNT(DISTINCT stage.stage_id) AS canonical_stage_count,
    COUNT(DISTINCT observation.observation_id) AS observation_count,
    SUM(CASE WHEN scan_file.required_for_completeness = 'Y' THEN 1 ELSE 0 END)
        AS required_file_count,
    MIN(scan_file.created_at) AS first_file_loaded_at,
    MAX(observation.created_at) AS last_observation_loaded_at
FROM scan_run run
LEFT JOIN scan_file
    ON scan_file.run_id = run.run_id
LEFT JOIN raw_cis_record raw_record
    ON raw_record.run_id = run.run_id
LEFT JOIN canonical_finding_stage stage
    ON stage.run_id = run.run_id
LEFT JOIN finding_observation observation
    ON observation.run_id = run.run_id
GROUP BY
    run.run_id,
    run.tenancy_id,
    run.status,
    run.started_at,
    run.completed_at,
    run.scanner_version,
    run.scanner_commit,
    run.wrapper_version,
    run.benchmark_version,
    run.manifest_checksum;
