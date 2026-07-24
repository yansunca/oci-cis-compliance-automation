-- Curated OAC reporting views.

CREATE OR REPLACE VIEW v_cis_current_findings AS
SELECT
    finding_id,
    tenancy_id,
    control_lineage_id,
    control_display_id,
    benchmark_version,
    scope_type,
    scope_key,
    region,
    current_state,
    priority,
    risk_score,
    owner,
    first_seen_at,
    last_seen_at,
    resolved_at,
    JSON_VALUE(product_json, '$.productId' NULL ON ERROR) AS product_id,
    JSON_VALUE(product_json, '$.displayName' NULL ON ERROR) AS product_display_name,
    JSON_VALUE(compartment_json, '$.path') AS compartment_path
FROM canonical_finding;

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
    raw_record_count,
    canonical_stage_count,
    observation_count
FROM vw_scan_run_health;

CREATE OR REPLACE VIEW v_cis_product_posture AS
SELECT
    COALESCE(JSON_VALUE(product_json, '$.productId' NULL ON ERROR), 'UNASSIGNED') AS product_id,
    COALESCE(JSON_VALUE(product_json, '$.displayName' NULL ON ERROR), 'Unassigned')
        AS product_display_name,
    priority,
    current_state,
    COUNT(*) AS finding_count
FROM canonical_finding
GROUP BY
    COALESCE(JSON_VALUE(product_json, '$.productId' NULL ON ERROR), 'UNASSIGNED'),
    COALESCE(JSON_VALUE(product_json, '$.displayName' NULL ON ERROR), 'Unassigned'),
    priority,
    current_state;

CREATE OR REPLACE VIEW v_cis_mapping_quality AS
SELECT
    mapping_quality_status,
    mapping_source,
    effective_product_id,
    COUNT(*) AS compartment_count
FROM vw_mapping_quality
GROUP BY
    mapping_quality_status,
    mapping_source,
    effective_product_id;

CREATE OR REPLACE VIEW v_cis_finding_history AS
SELECT
    observation.finding_id,
    observation.run_id,
    observation.source_file,
    observation.source_row,
    observation.schema_hash,
    observation.scanner_version,
    observation.benchmark_version,
    observation.normalizer_version,
    observation.configuration_version,
    observation.observed_at
FROM finding_observation observation;
