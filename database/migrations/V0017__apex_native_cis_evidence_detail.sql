-- APEX native CIS evidence detail.
-- Extends Finding Detail with source CIS report fields and original artifact
-- locators for read-only audit review.

whenever sqlerror exit sql.sqlcode rollback

CREATE OR REPLACE VIEW v_cis_apex_finding_detail AS
SELECT
    queue.finding_id,
    queue.tenancy_id,
    queue.control_display_id,
    queue.control_lineage_id,
    queue.benchmark_version,
    queue.current_state,
    queue.priority,
    queue.risk_score,
    queue.owner,
    queue.product_id,
    queue.product_display_name,
    queue.product_mapping_source,
    queue.resource_type,
    queue.resource_name,
    queue.region,
    queue.compartment_ocid,
    queue.compartment_name,
    queue.compartment_path,
    queue.last_observed_run_id,
    queue.last_source_file,
    queue.last_source_row,
    queue.last_schema_hash,
    queue.first_seen_at,
    queue.last_seen_at,
    queue.due_at,
    queue.due_status,
    queue.age_days,
    queue.apex_detail_key,
    COALESCE(
        audit_report.native_detail_csv_link,
        audit_report.native_html_summary_link,
        queue.evidence_locator
    ) AS evidence_locator,
    audit_report.run_status,
    audit_report.scanner_version,
    audit_report.scanner_commit,
    audit_report.wrapper_version,
    audit_report.normalizer_version,
    audit_report.configuration_version,
    audit_report.recommendation_number,
    audit_report.cis_section,
    audit_report.cis_level,
    audit_report.recommendation_title,
    audit_report.cis_result,
    audit_report.native_findings_count,
    audit_report.native_compliant_items,
    audit_report.native_total_count,
    audit_report.native_compliance_percentage,
    audit_report.evidence_summary,
    audit_report.remediation,
    audit_report.source_file AS native_source_file,
    audit_report.source_row AS native_source_row,
    audit_report.schema_hash AS native_schema_hash,
    audit_report.manifest_checksum,
    audit_report.native_html_summary_link,
    audit_report.native_summary_csv_link,
    audit_report.native_detail_csv_link,
    audit_report.native_error_csv_link,
    audit_report.source_artifact_locator
FROM v_cis_apex_work_queue queue
LEFT JOIN v_cis_audit_report_view audit_report
    ON audit_report.finding_id = queue.finding_id
    AND audit_report.run_id = queue.last_observed_run_id;

CREATE OR REPLACE VIEW v_cis_apex_finding_evidence AS
SELECT
    finding_id,
    last_observed_run_id AS run_id,
    run_status,
    scanner_version,
    benchmark_version,
    wrapper_version,
    normalizer_version,
    configuration_version,
    recommendation_number,
    cis_section,
    cis_level,
    recommendation_title,
    cis_result,
    native_findings_count,
    native_compliant_items,
    native_total_count,
    native_compliance_percentage,
    evidence_summary,
    remediation,
    native_source_file,
    native_source_row,
    native_schema_hash,
    manifest_checksum,
    native_html_summary_link,
    native_summary_csv_link,
    native_detail_csv_link,
    native_error_csv_link,
    source_artifact_locator,
    evidence_locator
FROM v_cis_apex_finding_detail;

GRANT SELECT ON v_cis_apex_finding_detail TO oci_cis_app;
GRANT SELECT ON v_cis_apex_finding_evidence TO oci_cis_app;
