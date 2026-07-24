-- Finding absence reconciliation package skeleton.
-- This package marks active findings resolved only after a complete, successful
-- run has been loaded and observed findings have been upserted.

CREATE OR REPLACE PACKAGE finding_absence_reconciliation AS
    PROCEDURE resolve_absent_for_run(p_run_id IN VARCHAR2);
END finding_absence_reconciliation;
/

CREATE OR REPLACE PACKAGE BODY finding_absence_reconciliation AS
    PROCEDURE resolve_absent_for_run(p_run_id IN VARCHAR2) IS
    BEGIN
        UPDATE canonical_finding target
        SET
            target.current_state = 'RESOLVED',
            target.resolved_at = (
                SELECT scan_run.completed_at
                FROM scan_run
                WHERE scan_run.run_id = p_run_id
            ),
            target.last_state_change_at = (
                SELECT scan_run.completed_at
                FROM scan_run
                WHERE scan_run.run_id = p_run_id
            ),
            target.updated_at = SYSTIMESTAMP
        WHERE target.current_state IN ('NEW', 'ACTIVE', 'REOPENED')
        AND EXISTS (
            SELECT 1
            FROM scan_run ready_run
            WHERE ready_run.run_id = p_run_id
            AND ready_run.status = 'SUCCESS'
            AND ready_run.completed_at IS NOT NULL
        )
        AND EXISTS (
            SELECT 1
            FROM canonical_finding_stage observed_scope
            WHERE observed_scope.run_id = p_run_id
            AND JSON_VALUE(observed_scope.canonical_json, '$.tenancyId') = target.tenancy_id
            AND JSON_VALUE(
                observed_scope.canonical_json,
                '$.control.benchmarkVersion'
            ) = target.benchmark_version
        )
        AND NOT EXISTS (
            SELECT 1
            FROM finding_observation observed
            WHERE observed.run_id = p_run_id
            AND observed.finding_id = target.finding_id
        )
        AND target.current_state NOT IN ('ACCEPTED_RISK', 'SUPPRESSED');
    END resolve_absent_for_run;
END finding_absence_reconciliation;
/
