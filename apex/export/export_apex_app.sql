-- Export an existing OCI CIS Findings Operations APEX application.
--
-- Usage from SQLcl/sqlplus:
--   sql ADMIN/<password>@<service> @apex/export/export_apex_app.sql <workspace_name> <application_id>
--
-- This script does not create the APEX app. Create the app in APEX Builder from the
-- page blueprint first, then use this script to produce the real APEX export SQL.

set define on
set serveroutput on
set feedback off
set heading off
set pagesize 0
set verify off
set long 100000000
set longchunksize 32767
set trimspool on
whenever sqlerror exit sql.sqlcode rollback

define workspace_name = '&1'
define application_id = '&2'

column export_file_name new_value export_file_name noprint
SELECT 'f' || '&application_id' || '_oci_cis_findings_operations_demo.sql' AS export_file_name
FROM dual;

DECLARE
    workspace_count NUMBER;
BEGIN
    SELECT COUNT(*)
    INTO workspace_count
    FROM apex_workspaces
    WHERE workspace = UPPER('&workspace_name');

    IF workspace_count = 0 THEN
        raise_application_error(-20051, 'APEX workspace not found: &workspace_name');
    END IF;
END;
/

spool &export_file_name

DECLARE
    export_files apex_t_export_files;
    export_content CLOB;
    offset_pos PLS_INTEGER;
BEGIN
    export_files := apex_export.get_application(
        p_application_id => TO_NUMBER('&application_id')
    );

    FOR file_index IN 1 .. export_files.COUNT LOOP
        export_content := export_files(file_index).contents;
        offset_pos := 1;

        WHILE offset_pos <= dbms_lob.getlength(export_content) LOOP
            dbms_output.put_line(dbms_lob.substr(export_content, 32000, offset_pos));
            offset_pos := offset_pos + 32000;
        END LOOP;
    END LOOP;
END;
/

spool off

prompt Exported &export_file_name
exit success
