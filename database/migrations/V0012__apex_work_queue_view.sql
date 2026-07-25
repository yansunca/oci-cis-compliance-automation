-- APEX-facing work queue view.
-- Keeps the APEX app insulated from canonical table/view changes by exposing a
-- stable read model for finding list and drill-down pages.

whenever sqlerror exit sql.sqlcode rollback

CREATE OR REPLACE VIEW v_cis_apex_work_queue AS
SELECT
    queue.finding_id,
    queue.tenancy_id,
    queue.control_lineage_id,
    queue.control_display_id,
    queue.benchmark_version,
    queue.scope_type,
    queue.scope_key,
    queue.region,
    queue.current_state,
    queue.priority,
    queue.risk_score,
    queue.owner,
    queue.first_seen_at,
    queue.last_seen_at,
    queue.last_state_change_at,
    queue.resolved_at,
    queue.due_at,
    CASE
        WHEN queue.current_state = 'RESOLVED' THEN 'RESOLVED'
        WHEN queue.due_at IS NULL THEN 'NO_DUE_DATE'
        WHEN queue.due_at < SYSTIMESTAMP THEN 'OVERDUE'
        WHEN queue.due_at < SYSTIMESTAMP + INTERVAL '7' DAY THEN 'DUE_SOON'
        ELSE 'ON_TRACK'
    END AS due_status,
    GREATEST(
        0,
        TRUNC(CAST(SYSTIMESTAMP AS DATE)) - TRUNC(CAST(queue.first_seen_at AS DATE))
    ) AS age_days,
    queue.product_id,
    queue.product_display_name,
    queue.product_mapping_source,
    queue.resource_type,
    queue.resource_name,
    queue.compartment_ocid,
    queue.compartment_name,
    queue.compartment_path,
    queue.last_observed_run_id,
    queue.last_source_file,
    queue.last_source_row,
    queue.last_schema_hash,
    queue.updated_at,
    queue.finding_id AS apex_detail_key,
    CASE
        WHEN queue.last_observed_run_id IS NOT NULL
             AND queue.last_source_file IS NOT NULL
        THEN 'oci-cis://' || queue.last_observed_run_id || '/files/' || queue.last_source_file
        ELSE NULL
    END AS evidence_locator
FROM vw_finding_work_queue queue;

GRANT SELECT ON v_cis_apex_work_queue TO oci_cis_app;
