-- Product enrichment package skeleton.
-- Writes effective product mapping into canonical_finding.product_json.

CREATE OR REPLACE PACKAGE product_enrichment AS
    PROCEDURE enrich_all;
    PROCEDURE enrich_finding(p_finding_id IN VARCHAR2);
END product_enrichment;
/

CREATE OR REPLACE PACKAGE BODY product_enrichment AS
    PROCEDURE enrich_all IS
    BEGIN
        UPDATE canonical_finding finding
        SET
            finding.product_json = (
                SELECT JSON_OBJECT(
                    'productId' VALUE mapping.effective_product_id,
                    'displayName' VALUE mapping.effective_product_name,
                    'mappingSource' VALUE mapping.mapping_source,
                    'sourceCompartmentOcid' VALUE mapping.compartment_id,
                    'tagNamespace' VALUE mapping.tag_namespace,
                    'tagKey' VALUE mapping.tag_key,
                    'tagValue' VALUE mapping.tag_value
                    RETURNING CLOB
                )
                FROM vw_compartment_product_mapping mapping
                WHERE mapping.compartment_id = JSON_VALUE(finding.compartment_json, '$.ocid')
            ),
            finding.updated_at = SYSTIMESTAMP
        WHERE EXISTS (
            SELECT 1
            FROM vw_compartment_product_mapping mapping
            WHERE mapping.compartment_id = JSON_VALUE(finding.compartment_json, '$.ocid')
        );

        UPDATE canonical_finding finding
        SET
            finding.product_json = JSON_OBJECT(
                'productId' VALUE 'UNASSIGNED',
                'displayName' VALUE 'Unassigned',
                'mappingSource' VALUE 'UNASSIGNED',
                'sourceCompartmentOcid' VALUE JSON_VALUE(finding.compartment_json, '$.ocid'),
                'tagNamespace' VALUE 'Operations',
                'tagKey' VALUE 'ProductId',
                'tagValue' VALUE NULL
                RETURNING CLOB
            ),
            finding.updated_at = SYSTIMESTAMP
        WHERE finding.product_json IS NULL;
    END enrich_all;

    PROCEDURE enrich_finding(p_finding_id IN VARCHAR2) IS
    BEGIN
        UPDATE canonical_finding finding
        SET
            finding.product_json = COALESCE(
                (
                    SELECT JSON_OBJECT(
                        'productId' VALUE mapping.effective_product_id,
                        'displayName' VALUE mapping.effective_product_name,
                        'mappingSource' VALUE mapping.mapping_source,
                        'sourceCompartmentOcid' VALUE mapping.compartment_id,
                        'tagNamespace' VALUE mapping.tag_namespace,
                        'tagKey' VALUE mapping.tag_key,
                        'tagValue' VALUE mapping.tag_value
                        RETURNING CLOB
                    )
                    FROM vw_compartment_product_mapping mapping
                    WHERE mapping.compartment_id = JSON_VALUE(finding.compartment_json, '$.ocid')
                ),
                JSON_OBJECT(
                    'productId' VALUE 'UNASSIGNED',
                    'displayName' VALUE 'Unassigned',
                    'mappingSource' VALUE 'UNASSIGNED',
                    'sourceCompartmentOcid' VALUE JSON_VALUE(finding.compartment_json, '$.ocid'),
                    'tagNamespace' VALUE 'Operations',
                    'tagKey' VALUE 'ProductId',
                    'tagValue' VALUE NULL
                    RETURNING CLOB
                )
            ),
            finding.updated_at = SYSTIMESTAMP
        WHERE finding.finding_id = p_finding_id;
    END enrich_finding;
END product_enrichment;
/
