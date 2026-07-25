-- APEX dashboard, product scorecard, and mapping quality compatibility views.
--
-- These views match the current APEX page contracts and are intentionally
-- derived from the canonical CIS finding model so pages remain populated even
-- before compartment snapshot/tag data is loaded.

whenever sqlerror exit sql.sqlcode rollback

CREATE OR REPLACE VIEW v_cis_dashboard_metric_cards AS
WITH latest_run AS (
    SELECT run_id, completed_at
    FROM scan_run
    ORDER BY completed_at DESC NULLS LAST, started_at DESC NULLS LAST
    FETCH FIRST 1 ROW ONLY
), metrics AS (
    SELECT 'SCAN_RUNS' AS metric_key, 'Scan runs' AS metric_label, COUNT(*) AS metric_value FROM scan_run
    UNION ALL SELECT 'TOTAL_FINDINGS', 'Total findings', COUNT(*) FROM canonical_finding
    UNION ALL SELECT 'OPEN_FINDINGS', 'Open findings', COUNT(*) FROM canonical_finding WHERE current_state <> 'RESOLVED'
    UNION ALL SELECT 'CRITICAL_FINDINGS', 'Critical findings', COUNT(*) FROM canonical_finding WHERE priority = 'CRITICAL'
    UNION ALL SELECT 'HIGH_FINDINGS', 'High findings', COUNT(*) FROM canonical_finding WHERE priority = 'HIGH'
    UNION ALL SELECT 'PRODUCTS', 'Products', COUNT(DISTINCT COALESCE(JSON_VALUE(product_json, '$.productId' NULL ON ERROR), 'UNASSIGNED')) FROM canonical_finding
    UNION ALL SELECT 'COMPARTMENTS', 'Compartments', COUNT(DISTINCT COALESCE(JSON_VALUE(compartment_json, '$.ocid' NULL ON ERROR), 'UNKNOWN')) FROM canonical_finding
)
SELECT
    metrics.metric_key,
    metrics.metric_label,
    metrics.metric_value,
    latest_run.run_id AS latest_run_id,
    latest_run.completed_at AS latest_completed_at
FROM metrics
CROSS JOIN latest_run;

CREATE OR REPLACE VIEW v_cis_product_scorecard AS
SELECT
    COALESCE(JSON_VALUE(product_json, '$.productId' NULL ON ERROR), 'UNASSIGNED') AS product_id,
    COALESCE(JSON_VALUE(product_json, '$.displayName' NULL ON ERROR), 'Unassigned') AS product_display_name,
    CAST(NULL AS VARCHAR2(255)) AS business_owner,
    CAST(NULL AS VARCHAR2(255)) AS technical_owner,
    CAST(NULL AS VARCHAR2(255)) AS sla_policy,
    CAST(NULL AS VARCHAR2(255)) AS routing_target,
    COUNT(*) AS finding_count,
    SUM(CASE WHEN current_state <> 'RESOLVED' THEN 1 ELSE 0 END) AS open_finding_count,
    SUM(CASE WHEN priority = 'CRITICAL' THEN 1 ELSE 0 END) AS critical_count,
    SUM(CASE WHEN priority = 'HIGH' THEN 1 ELSE 0 END) AS high_count,
    SUM(CASE WHEN priority = 'MEDIUM' THEN 1 ELSE 0 END) AS medium_count,
    SUM(CASE WHEN priority = 'LOW' THEN 1 ELSE 0 END) AS low_count,
    SUM(CASE WHEN priority NOT IN ('CRITICAL','HIGH','MEDIUM','LOW') OR priority IS NULL THEN 1 ELSE 0 END) AS informational_count,
    MIN(first_seen_at) AS oldest_first_seen_at,
    MAX(last_seen_at) AS latest_last_seen_at
FROM canonical_finding
GROUP BY
    COALESCE(JSON_VALUE(product_json, '$.productId' NULL ON ERROR), 'UNASSIGNED'),
    COALESCE(JSON_VALUE(product_json, '$.displayName' NULL ON ERROR), 'Unassigned');

CREATE OR REPLACE VIEW v_cis_mapping_quality_detail AS
WITH finding_compartments AS (
    SELECT DISTINCT
        JSON_VALUE(compartment_json, '$.ocid' NULL ON ERROR) AS compartment_id,
        tenancy_id,
        JSON_VALUE(compartment_json, '$.name' NULL ON ERROR) AS compartment_name,
        JSON_VALUE(compartment_json, '$.path' NULL ON ERROR) AS compartment_path,
        JSON_VALUE(product_json, '$.productId' NULL ON ERROR) AS effective_product_id,
        JSON_VALUE(product_json, '$.displayName' NULL ON ERROR) AS effective_product_name,
        JSON_VALUE(product_json, '$.mappingSource' NULL ON ERROR) AS mapping_source,
        JSON_VALUE(product_json, '$.tagNamespace' NULL ON ERROR) AS tag_namespace,
        JSON_VALUE(product_json, '$.tagKey' NULL ON ERROR) AS tag_key,
        JSON_VALUE(product_json, '$.tagValue' NULL ON ERROR) AS tag_value
    FROM canonical_finding
)
SELECT
    COALESCE(mapping.compartment_id, finding_compartments.compartment_id) AS compartment_id,
    COALESCE(mapping.tenancy_id, finding_compartments.tenancy_id) AS tenancy_id,
    COALESCE(mapping.compartment_name, finding_compartments.compartment_name) AS compartment_name,
    COALESCE(mapping.compartment_path, finding_compartments.compartment_path) AS compartment_path,
    COALESCE(mapping.effective_product_id, finding_compartments.effective_product_id, 'UNASSIGNED') AS effective_product_id,
    COALESCE(mapping.effective_product_name, finding_compartments.effective_product_name, 'Unassigned') AS effective_product_name,
    COALESCE(mapping.mapping_source, finding_compartments.mapping_source, 'UNASSIGNED') AS mapping_source,
    COALESCE(mapping.mapping_quality_status,
        CASE WHEN COALESCE(finding_compartments.effective_product_id, 'UNASSIGNED') = 'UNASSIGNED'
             THEN 'NEEDS_PRODUCT_TAG'
             ELSE 'MAPPED'
        END) AS mapping_quality_status,
    COALESCE(mapping.tag_namespace, finding_compartments.tag_namespace) AS tag_namespace,
    COALESCE(mapping.tag_key, finding_compartments.tag_key) AS tag_key,
    COALESCE(mapping.tag_value, finding_compartments.tag_value) AS tag_value,
    mapping.override_id,
    mapping.override_reason,
    CASE WHEN COALESCE(mapping.effective_product_id, finding_compartments.effective_product_id, 'UNASSIGNED') = 'UNASSIGNED'
         THEN 'Y'
         ELSE 'N'
    END AS needs_attention
FROM finding_compartments
FULL OUTER JOIN vw_mapping_quality mapping
    ON mapping.compartment_id = finding_compartments.compartment_id;

GRANT SELECT ON v_cis_dashboard_metric_cards TO oci_cis_app;
GRANT SELECT ON v_cis_product_scorecard TO oci_cis_app;
GRANT SELECT ON v_cis_mapping_quality_detail TO oci_cis_app;
