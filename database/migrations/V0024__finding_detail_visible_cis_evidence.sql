-- Surface native CIS report evidence in the existing Finding Detail column.
--
-- APEX Interactive Report users can retain saved report layouts. This keeps the
-- already-visible evidence column audit-friendly even when optional native CIS
-- detail columns are hidden by a saved report.

whenever sqlerror exit sql.sqlcode rollback

CREATE OR REPLACE VIEW v_cis_apex_finding_detail AS
WITH artifact_roles AS (
    SELECT
        run_id,
        MAX(CASE WHEN artifact_role = 'NATIVE_HTML_SUMMARY' THEN download_url END)
            AS native_html_summary_download_url,
        MAX(CASE WHEN artifact_role = 'NATIVE_SUMMARY_CSV' THEN download_url END)
            AS native_summary_csv_download_url,
        MAX(CASE WHEN artifact_role = 'NATIVE_ERROR_CSV' THEN download_url END)
            AS native_error_csv_download_url
    FROM v_cis_evidence_artifact_downloads
    GROUP BY run_id
),
evidence_choices AS (
    SELECT
        queue.finding_id,
        detail_artifact.download_url AS detail_download_url,
        COALESCE(
            detail_artifact.download_url,
            artifact_roles.native_html_summary_download_url,
            artifact_roles.native_summary_csv_download_url,
            artifact_roles.native_error_csv_download_url
        ) AS best_download_url,
        CASE
            WHEN detail_artifact.download_url IS NOT NULL THEN 'Open Detail CSV'
            WHEN artifact_roles.native_html_summary_download_url IS NOT NULL THEN 'Open HTML Summary'
            WHEN artifact_roles.native_summary_csv_download_url IS NOT NULL THEN 'Open Summary CSV'
            WHEN artifact_roles.native_error_csv_download_url IS NOT NULL THEN 'Open Error CSV'
            ELSE NULL
        END AS best_download_label,
        CASE
            WHEN detail_artifact.download_url IS NOT NULL THEN 'NATIVE_DETAIL_CSV'
            WHEN artifact_roles.native_html_summary_download_url IS NOT NULL THEN 'NATIVE_HTML_SUMMARY'
            WHEN artifact_roles.native_summary_csv_download_url IS NOT NULL THEN 'NATIVE_SUMMARY_CSV'
            WHEN artifact_roles.native_error_csv_download_url IS NOT NULL THEN 'NATIVE_ERROR_CSV'
            ELSE NULL
        END AS best_download_type
    FROM v_cis_apex_work_queue queue
    LEFT JOIN v_cis_audit_report_view audit_report
        ON audit_report.finding_id = queue.finding_id
        AND audit_report.run_id = queue.last_observed_run_id
    LEFT JOIN artifact_roles
        ON artifact_roles.run_id = queue.last_observed_run_id
    LEFT JOIN v_cis_evidence_artifact_downloads detail_artifact
        ON detail_artifact.run_id = audit_report.run_id
        AND detail_artifact.artifact_file_name = audit_report.source_file
        AND detail_artifact.artifact_role = 'NATIVE_DETAIL_CSV'
)
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
    'Control ' || queue.control_display_id
        || ' | Result: ' || COALESCE(audit_report.cis_result, queue.current_state, 'UNKNOWN')
        || ' | Source: ' || COALESCE(audit_report.source_file, queue.last_source_file, 'CIS report')
        || CASE
            WHEN COALESCE(audit_report.source_row, queue.last_source_row) IS NOT NULL
            THEN ':' || COALESCE(audit_report.source_row, queue.last_source_row)
            ELSE ''
        END
        || ' | Open: ' || COALESCE(evidence_choices.best_download_label, 'CIS evidence')
        AS evidence_locator,
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
    artifact_roles.native_html_summary_download_url,
    artifact_roles.native_summary_csv_download_url,
    COALESCE(
        evidence_choices.detail_download_url,
        artifact_roles.native_html_summary_download_url
    ) AS native_detail_csv_download_url,
    evidence_choices.best_download_label AS native_detail_csv_download_label,
    evidence_choices.best_download_url AS native_best_evidence_download_url,
    evidence_choices.best_download_label AS native_best_evidence_download_label,
    evidence_choices.best_download_type AS native_best_evidence_download_type,
    artifact_roles.native_error_csv_download_url,
    audit_report.source_artifact_locator
FROM v_cis_apex_work_queue queue
LEFT JOIN v_cis_audit_report_view audit_report
    ON audit_report.finding_id = queue.finding_id
    AND audit_report.run_id = queue.last_observed_run_id
LEFT JOIN artifact_roles
    ON artifact_roles.run_id = queue.last_observed_run_id
LEFT JOIN evidence_choices
    ON evidence_choices.finding_id = queue.finding_id;

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
    native_html_summary_download_url,
    native_summary_csv_download_url,
    native_detail_csv_download_url,
    native_detail_csv_download_label,
    native_best_evidence_download_url,
    native_best_evidence_download_label,
    native_best_evidence_download_type,
    native_error_csv_download_url,
    source_artifact_locator,
    evidence_locator
FROM v_cis_apex_finding_detail;

GRANT SELECT ON v_cis_apex_finding_detail TO oci_cis_app;
GRANT SELECT ON v_cis_apex_finding_evidence TO oci_cis_app;
