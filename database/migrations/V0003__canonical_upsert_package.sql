-- Canonical finding upsert package skeleton.
-- This package is the reviewed merge boundary from canonical_finding_stage into
-- durable finding and observation tables. It is intentionally table-local: no
-- OCI calls, no external network calls, and no credential handling.

CREATE OR REPLACE PACKAGE canonical_finding_upsert AS
    PROCEDURE upsert_run(p_run_id IN VARCHAR2);
END canonical_finding_upsert;
/

CREATE OR REPLACE PACKAGE BODY canonical_finding_upsert AS
    PROCEDURE upsert_run(p_run_id IN VARCHAR2) IS
    BEGIN
        MERGE INTO canonical_finding target
        USING (
            SELECT
                stage.finding_id,
                JSON_VALUE(stage.canonical_json, '$.tenancyId') AS tenancy_id,
                JSON_VALUE(stage.canonical_json, '$.control.lineageId')
                    AS control_lineage_id,
                JSON_VALUE(stage.canonical_json, '$.control.displayId')
                    AS control_display_id,
                JSON_VALUE(stage.canonical_json, '$.control.benchmarkVersion')
                    AS benchmark_version,
                JSON_VALUE(stage.canonical_json, '$.scope.type') AS scope_type,
                JSON_VALUE(stage.canonical_json, '$.scope.key') AS scope_key,
                JSON_VALUE(stage.canonical_json, '$.scope.region' NULL ON ERROR) AS region,
                JSON_VALUE(stage.canonical_json, '$.state') AS finding_state,
                JSON_VALUE(stage.canonical_json, '$.priority') AS priority,
                JSON_VALUE(stage.canonical_json, '$.riskScore' RETURNING NUMBER NULL ON ERROR)
                    AS risk_score,
                JSON_VALUE(stage.canonical_json, '$.owner' NULL ON ERROR) AS owner,
                TO_TIMESTAMP_TZ(
                    REPLACE(JSON_VALUE(stage.canonical_json, '$.firstSeenAt'), 'Z', '+00:00'),
                    'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'
                ) AS first_seen_at,
                TO_TIMESTAMP_TZ(
                    REPLACE(JSON_VALUE(stage.canonical_json, '$.lastSeenAt'), 'Z', '+00:00'),
                    'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'
                ) AS last_seen_at,
                TO_TIMESTAMP_TZ(
                    REPLACE(
                        JSON_VALUE(stage.canonical_json, '$.lastStateChangeAt' NULL ON ERROR),
                        'Z',
                        '+00:00'
                    ),
                    'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'
                ) AS last_state_change_at,
                TO_TIMESTAMP_TZ(
                    REPLACE(
                        JSON_VALUE(stage.canonical_json, '$.resolvedAt' NULL ON ERROR),
                        'Z',
                        '+00:00'
                    ),
                    'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'
                ) AS resolved_at,
                TO_TIMESTAMP_TZ(
                    REPLACE(JSON_VALUE(stage.canonical_json, '$.dueAt' NULL ON ERROR), 'Z', '+00:00'),
                    'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'
                ) AS due_at,
                JSON_QUERY(stage.canonical_json, '$.product' RETURNING CLOB NULL ON ERROR)
                    AS product_json,
                JSON_QUERY(stage.canonical_json, '$.resource' RETURNING CLOB NULL ON ERROR)
                    AS resource_json,
                JSON_QUERY(stage.canonical_json, '$.compartment' RETURNING CLOB)
                    AS compartment_json,
                JSON_QUERY(stage.canonical_json, '$.attributes' RETURNING CLOB NULL ON ERROR)
                    AS attributes_json,
                JSON_VALUE(stage.canonical_json, '$.evidenceSummary' NULL ON ERROR)
                    AS evidence_summary,
                JSON_VALUE(stage.canonical_json, '$.remediation' NULL ON ERROR) AS remediation
            FROM canonical_finding_stage stage
            WHERE stage.run_id = p_run_id
        ) source
        ON (target.finding_id = source.finding_id)
        WHEN MATCHED THEN UPDATE SET
            target.current_state = CASE
                WHEN target.current_state IN ('ACCEPTED_RISK', 'SUPPRESSED')
                    THEN target.current_state
                WHEN target.current_state IN ('RESOLVED', 'NOT_ASSESSED')
                    AND source.finding_state IN ('NEW', 'ACTIVE')
                    THEN 'REOPENED'
                WHEN target.current_state IN ('NEW', 'ACTIVE', 'REOPENED')
                    AND source.finding_state IN ('NEW', 'ACTIVE')
                    THEN 'ACTIVE'
                ELSE source.finding_state
            END,
            target.priority = source.priority,
            target.risk_score = source.risk_score,
            target.owner = source.owner,
            target.last_seen_at = source.last_seen_at,
            target.last_state_change_at = source.last_state_change_at,
            target.resolved_at = source.resolved_at,
            target.due_at = source.due_at,
            target.product_json = source.product_json,
            target.resource_json = source.resource_json,
            target.compartment_json = source.compartment_json,
            target.attributes_json = source.attributes_json,
            target.evidence_summary = source.evidence_summary,
            target.remediation = source.remediation,
            target.updated_at = SYSTIMESTAMP
        WHEN NOT MATCHED THEN INSERT (
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
            last_state_change_at,
            resolved_at,
            due_at,
            product_json,
            resource_json,
            compartment_json,
            attributes_json,
            evidence_summary,
            remediation
        ) VALUES (
            source.finding_id,
            source.tenancy_id,
            source.control_lineage_id,
            source.control_display_id,
            source.benchmark_version,
            source.scope_type,
            source.scope_key,
            source.region,
            source.finding_state,
            source.priority,
            source.risk_score,
            source.owner,
            source.first_seen_at,
            source.last_seen_at,
            source.last_state_change_at,
            source.resolved_at,
            source.due_at,
            source.product_json,
            source.resource_json,
            source.compartment_json,
            source.attributes_json,
            source.evidence_summary,
            source.remediation
        );

        INSERT INTO finding_observation (
            finding_id,
            run_id,
            source_file,
            source_row,
            schema_hash,
            scanner_version,
            benchmark_version,
            normalizer_version,
            configuration_version,
            observed_at,
            canonical_json
        )
        SELECT
            stage.finding_id,
            stage.run_id,
            stage.source_file,
            stage.source_row,
            JSON_VALUE(stage.canonical_json, '$.sourceLineage.schemaHash'),
            JSON_VALUE(stage.canonical_json, '$.sourceLineage.scannerVersion'),
            JSON_VALUE(stage.canonical_json, '$.sourceLineage.benchmarkVersion'),
            JSON_VALUE(stage.canonical_json, '$.sourceLineage.normalizerVersion' NULL ON ERROR),
            JSON_VALUE(stage.canonical_json, '$.sourceLineage.configurationVersion'),
            TO_TIMESTAMP_TZ(
                REPLACE(JSON_VALUE(stage.canonical_json, '$.lastSeenAt'), 'Z', '+00:00'),
                'YYYY-MM-DD"T"HH24:MI:SSTZH:TZM'
            ),
            stage.canonical_json
        FROM canonical_finding_stage stage
        WHERE stage.run_id = p_run_id
        AND NOT EXISTS (
            SELECT 1
            FROM finding_observation existing
            WHERE existing.finding_id = stage.finding_id
            AND existing.run_id = stage.run_id
            AND existing.source_file = stage.source_file
            AND existing.source_row = stage.source_row
        );
    END upsert_run;
END canonical_finding_upsert;
/
