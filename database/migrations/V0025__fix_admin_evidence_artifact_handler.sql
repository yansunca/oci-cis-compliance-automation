-- Fix the ORDS evidence artifact download endpoint.
--
-- APEX links use the OCI_CIS_APP ORDS schema mapping at
-- /ords/oci_cis_app/cis-evidence/artifact/:artifact_id. The handler reads
-- the application schema cache explicitly so report evidence is served from
-- the same schema where the loader stores it.

whenever sqlerror exit sql.sqlcode rollback

BEGIN
    ORDS.DELETE_MODULE(p_module_name => 'cis-evidence');
EXCEPTION
    WHEN OTHERS THEN
        NULL;
END;
/

BEGIN
    ORDS.DEFINE_MODULE(
        p_module_name => 'cis-evidence',
        p_base_path => 'cis-evidence/',
        p_items_per_page => 25,
        p_status => 'PUBLISHED',
        p_comments => 'Download immutable native CIS evidence artifacts by artifact id.'
    );

    ORDS.DEFINE_TEMPLATE(
        p_module_name => 'cis-evidence',
        p_pattern => 'artifact/:artifact_id'
    );

    ORDS.DEFINE_HANDLER(
        p_module_name => 'cis-evidence',
        p_pattern => 'artifact/:artifact_id',
        p_method => 'GET',
        p_source_type => ORDS.source_type_plsql,
        p_source => q'[
DECLARE
    l_blob BLOB;
    l_mime_type VARCHAR2(255);
    l_file_name VARCHAR2(512);
BEGIN
    SELECT
        content_blob,
        mime_type,
        artifact_file_name
    INTO
        l_blob,
        l_mime_type,
        l_file_name
    FROM OCI_CIS_APP.cis_evidence_artifact_cache
    WHERE artifact_id = TO_NUMBER(:artifact_id)
    AND status = 'ACTIVE';

    OWA_UTIL.mime_header(l_mime_type, FALSE);
    HTP.p('Content-Length: ' || DBMS_LOB.getlength(l_blob));
    HTP.p('Content-Disposition: inline; filename="' || REPLACE(l_file_name, '"', '') || '"');
    OWA_UTIL.http_header_close;
    WPG_DOCLOAD.download_file(l_blob);
EXCEPTION
    WHEN NO_DATA_FOUND THEN
        :status_code := 404;
        OWA_UTIL.mime_header('text/plain', FALSE);
        OWA_UTIL.http_header_close;
        HTP.p('Artifact not found');
    WHEN VALUE_ERROR THEN
        :status_code := 400;
        OWA_UTIL.mime_header('text/plain', FALSE);
        OWA_UTIL.http_header_close;
        HTP.p('Invalid artifact id');
END;
]',
        p_items_per_page => 0,
        p_comments => 'Streams a cached native CIS report artifact.'
    );

    COMMIT;
END;
/
