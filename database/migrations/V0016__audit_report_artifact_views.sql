-- CIS audit-oriented reporting and original native artifact link views.
-- These views keep APEX/OAC audit pages on stable SQL interfaces instead of
-- parsing native report files or raw JSON directly.

CREATE OR REPLACE VIEW v_cis_source_artifact_links AS
SELECT
    scan_file.run_id,
    scan_file.source_path,
    scan_file.category,
    scan_file.file_format,
    scan_file.checksum,
    scan_file.size_bytes,
    scan_file.row_count,
    scan_file.schema_hash,
    scan_file.control_hint,
    'artifact:' || scan_file.run_id || ':' || scan_file.source_path
        AS authorized_artifact_locator,
    CASE
        WHEN scan_file.category = 'REPORT' AND scan_file.file_format = 'HTML'
            THEN 'NATIVE_HTML_SUMMARY'
        WHEN scan_file.category = 'SUMMARY' AND scan_file.file_format = 'CSV'
            THEN 'NATIVE_SUMMARY_CSV'
        WHEN scan_file.category = 'DETAIL' AND scan_file.file_format = 'CSV'
            THEN 'NATIVE_DETAIL_CSV'
        WHEN scan_file.source_path LIKE '%error_report.csv'
            THEN 'NATIVE_ERROR_CSV'
        ELSE scan_file.category || '_' || scan_file.file_format
    END AS artifact_role,
    scan_file.created_at
FROM scan_file;

CREATE OR REPLACE VIEW v_cis_audit_report_view AS
WITH latest_observation AS (
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
        observation.observed_at,
        observation.canonical_json,
        ROW_NUMBER() OVER (
            PARTITION BY observation.finding_id
            ORDER BY observation.observed_at DESC, observation.observation_id DESC
        ) AS row_rank
    FROM finding_observation observation
)
SELECT
    finding.finding_id,
    finding.tenancy_id,
    observation.run_id,
    run.status AS run_status,
    run.started_at,
    run.completed_at,
    observation.scanner_version,
    run.scanner_commit,
    run.wrapper_version,
    observation.normalizer_version,
    observation.configuration_version,
    finding.benchmark_version,
    finding.control_display_id AS recommendation_number,
    JSON_VALUE(observation.canonical_json, '$.control.section' NULL ON ERROR)
        AS cis_section,
    JSON_VALUE(observation.canonical_json, '$.control.cisLevel' NULL ON ERROR)
        AS cis_level,
    JSON_VALUE(observation.canonical_json, '$.control.title' NULL ON ERROR)
        AS recommendation_title,
    JSON_VALUE(observation.canonical_json, '$.attributes.cisAudit.result' NULL ON ERROR)
        AS cis_result,
    JSON_VALUE(observation.canonical_json, '$.attributes.cisAudit.findings' NULL ON ERROR)
        AS native_findings_count,
    JSON_VALUE(observation.canonical_json, '$.attributes.cisAudit.compliantItems' NULL ON ERROR)
        AS native_compliant_items,
    JSON_VALUE(observation.canonical_json, '$.attributes.cisAudit.total' NULL ON ERROR)
        AS native_total_count,
    JSON_VALUE(
        observation.canonical_json,
        '$.attributes.cisAudit.compliancePercentage' NULL ON ERROR
    ) AS native_compliance_percentage,
    finding.current_state,
    finding.priority,
    finding.risk_score,
    finding.owner,
    JSON_VALUE(finding.product_json, '$.productId' NULL ON ERROR) AS product_id,
    JSON_VALUE(finding.product_json, '$.displayName' NULL ON ERROR) AS product_display_name,
    JSON_VALUE(finding.product_json, '$.mappingSource' NULL ON ERROR) AS product_mapping_source,
    JSON_VALUE(finding.resource_json, '$.type' NULL ON ERROR) AS resource_type,
    JSON_VALUE(finding.resource_json, '$.name' NULL ON ERROR) AS resource_name,
    finding.scope_type,
    finding.scope_key,
    finding.region,
    JSON_VALUE(finding.compartment_json, '$.ocid' NULL ON ERROR) AS compartment_ocid,
    JSON_VALUE(finding.compartment_json, '$.name' NULL ON ERROR) AS compartment_name,
    JSON_VALUE(finding.compartment_json, '$.path' NULL ON ERROR) AS compartment_path,
    finding.first_seen_at,
    finding.last_seen_at,
    finding.last_state_change_at,
    finding.resolved_at,
    finding.due_at,
    CASE
        WHEN finding.current_state NOT IN ('NEW', 'ACTIVE', 'REOPENED') THEN 'CLOSED'
        WHEN finding.due_at IS NOT NULL AND finding.due_at < SYSTIMESTAMP THEN 'OVERDUE'
        WHEN finding.due_at IS NOT NULL AND finding.due_at < SYSTIMESTAMP + INTERVAL '7' DAY
            THEN 'DUE_SOON'
        ELSE 'ON_TRACK'
    END AS due_status,
    FLOOR(CAST(SYSTIMESTAMP AS DATE) - CAST(finding.first_seen_at AS DATE))
        AS unresolved_age_days,
    finding.evidence_summary,
    finding.remediation,
    observation.source_file,
    observation.source_row,
    observation.schema_hash,
    run.manifest_checksum,
    JSON_VALUE(
        observation.canonical_json,
        '$.attributes.nativeReportLinks.nativeHtmlSummary' NULL ON ERROR
    ) AS native_html_summary_link,
    JSON_VALUE(
        observation.canonical_json,
        '$.attributes.nativeReportLinks.nativeSummaryCsv' NULL ON ERROR
    ) AS native_summary_csv_link,
    JSON_VALUE(
        observation.canonical_json,
        '$.attributes.nativeReportLinks.nativeDetailCsv' NULL ON ERROR
    ) AS native_detail_csv_link,
    JSON_VALUE(
        observation.canonical_json,
        '$.attributes.nativeReportLinks.nativeErrorCsv' NULL ON ERROR
    ) AS native_error_csv_link,
    'artifact:' || observation.run_id || ':reports/' || observation.source_file
        AS source_artifact_locator,
    'apex:finding:' || finding.finding_id AS apex_detail_key,
    'apex:run:' || observation.run_id AS apex_run_key
FROM canonical_finding finding
JOIN latest_observation observation
    ON observation.finding_id = finding.finding_id
    AND observation.row_rank = 1
JOIN scan_run run
    ON run.run_id = observation.run_id;

GRANT SELECT ON v_cis_source_artifact_links TO oci_cis_app;
GRANT SELECT ON v_cis_audit_report_view TO oci_cis_app;
