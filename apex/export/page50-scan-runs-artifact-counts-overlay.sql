prompt --application/page_00050_scan_runs_artifact_counts_overlay
set define off verify off feedback off
whenever sqlerror exit sql.sqlcode rollback

begin
    apex_util.set_security_group_id(
        apex_util.find_security_group_id(p_workspace => 'OCI_CIS_FINDINGS')
    );
    apex_application_install.set_workspace('OCI_CIS_FINDINGS');
    apex_application_install.set_application_id(100);
    apex_application_install.set_application_alias('OCI-CIS-FINDINGS-OPERATIONS');
    apex_application_install.set_application_name('OCI CIS Findings Operations');
    apex_application_install.set_schema('OCI_CIS_APP');
end;
/

begin
wwv_flow_imp.import_begin (
 p_version_yyyy_mm_dd=>'2024.11.30'
,p_release=>'24.2.17'
,p_default_workspace_id=>9682523043517848
,p_default_application_id=>100
,p_default_id_offset=>0
,p_default_owner=>'OCI_CIS_APP'
);
end;
/

begin
    wwv_flow_imp_page.remove_page(
        p_flow_id => 100,
        p_page_id => 50
    );
end;
/

begin
wwv_flow_imp_page.create_page(
 p_id=>50
,p_name=>'Scan Runs'
,p_alias=>'SCAN-RUNS'
,p_step_title=>'Scan Runs'
,p_autocomplete_on_off=>'OFF'
,p_page_template_options=>'#DEFAULT#'
,p_protection_level=>'C'
,p_page_component_map=>'18'
);

wwv_flow_imp_page.create_page_plug(
 p_id=>wwv_flow_imp.id(100500000000001)
,p_plug_name=>'Breadcrumb'
,p_region_template_options=>'#DEFAULT#:t-BreadcrumbRegion--useBreadcrumbTitle'
,p_component_template_options=>'#DEFAULT#'
,p_plug_template=>2531463326621247859
,p_plug_display_sequence=>10
,p_plug_display_point=>'REGION_POSITION_01'
,p_menu_id=>wwv_flow_imp.id(9689770221559249)
,p_plug_source_type=>'NATIVE_BREADCRUMB'
,p_menu_template_id=>4072363345357175094
);

wwv_flow_imp_page.create_page_plug(
 p_id=>wwv_flow_imp.id(100500000000010)
,p_plug_name=>'Scan Runs'
,p_region_template_options=>'#DEFAULT#:t-IRR-region--hideHeader js-addHiddenHeadingRoleDesc'
,p_plug_template=>2100526641005906379
,p_plug_display_sequence=>10
,p_query_type=>'SQL'
,p_plug_source=>wwv_flow_string.join(wwv_flow_t_varchar2(
'select',
'    run_id,',
'    tenancy_id,',
'    status,',
'    started_at,',
'    completed_at,',
'    scanner_version,',
'    benchmark_version,',
'    native_report_file_count,',
'    app_audit_artifact_count,',
'    indexed_artifact_count,',
'    raw_record_count,',
'    canonical_stage_count,',
'    observation_count',
'from oci_cis_app.v_cis_scan_summary'))
,p_include_rowid_column=>false
,p_plug_source_type=>'NATIVE_IR'
,p_prn_page_header=>'Scan Runs'
);

wwv_flow_imp_page.create_worksheet(
 p_id=>wwv_flow_imp.id(100500000000011)
,p_name=>'Scan Runs'
,p_max_row_count_message=>'The maximum row count for this report is #MAX_ROW_COUNT# rows. Please apply a filter to reduce the number of records in your query.'
,p_no_data_found_message=>'No data found.'
,p_pagination_type=>'ROWS_X_TO_Y'
,p_pagination_display_pos=>'BOTTOM_RIGHT'
,p_report_list_mode=>'TABS'
,p_lazy_loading=>false
,p_show_detail_link=>'N'
,p_show_notify=>'Y'
,p_download_formats=>'CSV:HTML:XLSX:PDF'
,p_enable_mail_download=>'Y'
,p_owner=>'OCI_CIS_APP'
,p_internal_uid=>100500000000011
);

wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100500000000012)
,p_db_column_name=>'RUN_ID'
,p_display_order=>10
,p_column_identifier=>'A'
,p_column_label=>'Run Id'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100500000000013)
,p_db_column_name=>'TENANCY_ID'
,p_display_order=>20
,p_column_identifier=>'B'
,p_column_label=>'Tenancy Id'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100500000000014)
,p_db_column_name=>'STATUS'
,p_display_order=>30
,p_column_identifier=>'C'
,p_column_label=>'Status'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100500000000015)
,p_db_column_name=>'STARTED_AT'
,p_display_order=>40
,p_column_identifier=>'D'
,p_column_label=>'Started At'
,p_column_type=>'DATE'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100500000000016)
,p_db_column_name=>'COMPLETED_AT'
,p_display_order=>50
,p_column_identifier=>'E'
,p_column_label=>'Completed At'
,p_column_type=>'DATE'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100500000000017)
,p_db_column_name=>'SCANNER_VERSION'
,p_display_order=>60
,p_column_identifier=>'F'
,p_column_label=>'Scanner Version'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100500000000018)
,p_db_column_name=>'BENCHMARK_VERSION'
,p_display_order=>70
,p_column_identifier=>'G'
,p_column_label=>'Benchmark Version'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100500000000019)
,p_db_column_name=>'NATIVE_REPORT_FILE_COUNT'
,p_display_order=>80
,p_column_identifier=>'H'
,p_column_label=>'Native Report Files'
,p_column_type=>'NUMBER'
,p_heading_alignment=>'RIGHT'
,p_column_alignment=>'RIGHT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100500000000020)
,p_db_column_name=>'APP_AUDIT_ARTIFACT_COUNT'
,p_display_order=>90
,p_column_identifier=>'I'
,p_column_label=>'App Audit Artifacts'
,p_column_type=>'NUMBER'
,p_heading_alignment=>'RIGHT'
,p_column_alignment=>'RIGHT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100500000000021)
,p_db_column_name=>'INDEXED_ARTIFACT_COUNT'
,p_display_order=>100
,p_column_identifier=>'J'
,p_column_label=>'Indexed Artifact Count'
,p_column_type=>'NUMBER'
,p_heading_alignment=>'RIGHT'
,p_column_alignment=>'RIGHT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100500000000022)
,p_db_column_name=>'RAW_RECORD_COUNT'
,p_display_order=>110
,p_column_identifier=>'K'
,p_column_label=>'Raw Record Count'
,p_column_type=>'NUMBER'
,p_heading_alignment=>'RIGHT'
,p_column_alignment=>'RIGHT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100500000000023)
,p_db_column_name=>'CANONICAL_STAGE_COUNT'
,p_display_order=>120
,p_column_identifier=>'L'
,p_column_label=>'Canonical Stage Count'
,p_column_type=>'NUMBER'
,p_heading_alignment=>'RIGHT'
,p_column_alignment=>'RIGHT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100500000000024)
,p_db_column_name=>'OBSERVATION_COUNT'
,p_display_order=>130
,p_column_identifier=>'M'
,p_column_label=>'Observation Count'
,p_column_type=>'NUMBER'
,p_heading_alignment=>'RIGHT'
,p_column_alignment=>'RIGHT'
);

wwv_flow_imp_page.create_worksheet_rpt(
 p_id=>wwv_flow_imp.id(100500000000030)
,p_application_user=>'APXWS_DEFAULT'
,p_report_seq=>10
,p_report_alias=>'SCAN_RUNS_AUDIT_COUNTS'
,p_status=>'PUBLIC'
,p_is_default=>'Y'
,p_report_columns=>'RUN_ID:TENANCY_ID:STATUS:STARTED_AT:COMPLETED_AT:SCANNER_VERSION:BENCHMARK_VERSION:NATIVE_REPORT_FILE_COUNT:APP_AUDIT_ARTIFACT_COUNT:INDEXED_ARTIFACT_COUNT:RAW_RECORD_COUNT:CANONICAL_STAGE_COUNT:OBSERVATION_COUNT'
);
end;
/

begin
wwv_flow_imp.import_end(
 p_auto_install_sup_obj=>nvl(wwv_flow_application_install.get_auto_install_sup_obj, false)
);
commit;
end;
/
