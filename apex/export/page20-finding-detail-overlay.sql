prompt --application/page_00020_finding_detail_overlay
set define off verify off feedback off
whenever sqlerror exit sql.sqlcode rollback

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
        p_page_id => 20
    );
end;
/

begin
wwv_flow_imp_page.create_page(
 p_id=>20
,p_name=>'Finding Detail'
,p_alias=>'FINDING-DETAIL'
,p_step_title=>'Finding Detail'
,p_autocomplete_on_off=>'OFF'
,p_page_template_options=>'#DEFAULT#'
,p_protection_level=>'C'
,p_page_component_map=>'18'
);
wwv_flow_imp_page.create_page_plug(
 p_id=>wwv_flow_imp.id(100200000000001)
,p_plug_name=>'Breadcrumb'
,p_region_template_options=>'#DEFAULT#:t-BreadcrumbRegion--useBreadcrumbTitle'
,p_plug_template=>2531463326621247859
,p_plug_display_sequence=>10
,p_plug_display_point=>'REGION_POSITION_01'
,p_menu_id=>wwv_flow_imp.id(9689770221559249)
,p_plug_source_type=>'NATIVE_BREADCRUMB'
,p_menu_template_id=>4072363345357175094
);
wwv_flow_imp_page.create_page_plug(
 p_id=>wwv_flow_imp.id(100200000000010)
,p_plug_name=>'Finding Detail'
,p_region_template_options=>'#DEFAULT#:t-IRR-region--hideHeader js-addHiddenHeadingRoleDesc'
,p_plug_template=>2100526641005906379
,p_plug_display_sequence=>10
,p_query_type=>'SQL'
,p_plug_source=>wwv_flow_string.join(wwv_flow_t_varchar2(
'select',
'    finding_id,',
'    control_display_id,',
'    current_state,',
'    priority,',
'    risk_score,',
'    product_display_name,',
'    recommendation_title,',
'    cis_section,',
'    cis_result,',
'    resource_type,',
'    resource_name,',
'    region,',
'    due_status,',
'    age_days,',
'    evidence_locator,',
'    evidence_summary,',
'    remediation,',
'    native_html_summary_link,',
'    native_summary_csv_link,',
'    native_detail_csv_link,',
'    native_error_csv_link,',
'    native_html_summary_download_url,',
'    native_summary_csv_download_url,',
'    native_detail_csv_download_url,',
'    native_detail_csv_download_label,',
'    native_best_evidence_download_url,',
'    native_best_evidence_download_label,',
'    native_best_evidence_download_type,',
'    native_error_csv_download_url,',
'    native_source_file,',
'    native_source_row,',
'    scanner_version,',
'    benchmark_version',
'from admin.v_cis_apex_finding_detail',
'where finding_id = :P20_FINDING_ID'))
,p_plug_source_type=>'NATIVE_IR'
,p_prn_page_header=>'Finding Detail'
);
wwv_flow_imp_page.create_page_item(
 p_id=>wwv_flow_imp.id(100200000000101)
,p_name=>'P20_FINDING_ID'
,p_item_sequence=>10
,p_item_plug_id=>wwv_flow_imp.id(100200000000010)
,p_prompt=>'Finding ID'
,p_display_as=>'NATIVE_HIDDEN'
,p_protection_level=>'S'
,p_attributes=>wwv_flow_t_plugin_attributes(wwv_flow_t_varchar2(
  'value_protected', 'N')).to_clob
);
wwv_flow_imp_page.create_worksheet(
 p_id=>wwv_flow_imp.id(100200000000011)
,p_name=>'Finding Detail'
,p_max_row_count_message=>'The maximum row count for this report is #MAX_ROW_COUNT# rows. Please apply a filter to reduce the number of records in your query.'
,p_no_data_found_message=>'No data found.'
,p_pagination_type=>'ROWS_X_TO_Y'
,p_report_list_mode=>'TABS'
,p_lazy_loading=>false
,p_show_detail_link=>'N'
,p_download_formats=>'CSV:HTML:XLSX:PDF'
,p_enable_mail_download=>'Y'
,p_owner=>'OCI_CIS_APP'
,p_internal_uid=>100200000000011
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000012)
,p_db_column_name=>'FINDING_ID'
,p_display_order=>10
,p_column_identifier=>'A'
,p_column_label=>'Finding Id'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000013)
,p_db_column_name=>'CONTROL_DISPLAY_ID'
,p_display_order=>20
,p_column_identifier=>'B'
,p_column_label=>'Control'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000014)
,p_db_column_name=>'CURRENT_STATE'
,p_display_order=>30
,p_column_identifier=>'C'
,p_column_label=>'Current State'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000015)
,p_db_column_name=>'PRIORITY'
,p_display_order=>40
,p_column_identifier=>'D'
,p_column_label=>'Priority'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000016)
,p_db_column_name=>'RISK_SCORE'
,p_display_order=>50
,p_column_identifier=>'E'
,p_column_label=>'Risk Score'
,p_column_type=>'NUMBER'
,p_heading_alignment=>'RIGHT'
,p_column_alignment=>'RIGHT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000017)
,p_db_column_name=>'PRODUCT_DISPLAY_NAME'
,p_display_order=>60
,p_column_identifier=>'F'
,p_column_label=>'Product'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000018)
,p_db_column_name=>'RESOURCE_TYPE'
,p_display_order=>70
,p_column_identifier=>'G'
,p_column_label=>'Resource Type'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000019)
,p_db_column_name=>'RESOURCE_NAME'
,p_display_order=>80
,p_column_identifier=>'H'
,p_column_label=>'Resource'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000020)
,p_db_column_name=>'REGION'
,p_display_order=>90
,p_column_identifier=>'I'
,p_column_label=>'Region'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000021)
,p_db_column_name=>'DUE_STATUS'
,p_display_order=>100
,p_column_identifier=>'J'
,p_column_label=>'Due Status'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000022)
,p_db_column_name=>'AGE_DAYS'
,p_display_order=>110
,p_column_identifier=>'K'
,p_column_label=>'Age Days'
,p_column_type=>'NUMBER'
,p_heading_alignment=>'RIGHT'
,p_column_alignment=>'RIGHT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000023)
,p_db_column_name=>'EVIDENCE_LOCATOR'
,p_display_order=>120
,p_column_identifier=>'L'
,p_column_label=>'Original Report Link'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000027)
,p_db_column_name=>'RECOMMENDATION_TITLE'
,p_display_order=>130
,p_column_identifier=>'P'
,p_column_label=>'CIS Recommendation'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000028)
,p_db_column_name=>'CIS_SECTION'
,p_display_order=>140
,p_column_identifier=>'Q'
,p_column_label=>'CIS Section'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000029)
,p_db_column_name=>'CIS_RESULT'
,p_display_order=>150
,p_column_identifier=>'R'
,p_column_label=>'CIS Result'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000032)
,p_db_column_name=>'EVIDENCE_SUMMARY'
,p_display_order=>160
,p_column_identifier=>'S'
,p_column_label=>'Evidence Summary'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000033)
,p_db_column_name=>'REMEDIATION'
,p_display_order=>170
,p_column_identifier=>'T'
,p_column_label=>'Remediation'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000034)
,p_db_column_name=>'NATIVE_HTML_SUMMARY_LINK'
,p_display_order=>180
,p_column_identifier=>'U'
,p_column_label=>'Native HTML Summary'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000035)
,p_db_column_name=>'NATIVE_SUMMARY_CSV_LINK'
,p_display_order=>190
,p_column_identifier=>'V'
,p_column_label=>'Native Summary CSV'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000036)
,p_db_column_name=>'NATIVE_DETAIL_CSV_LINK'
,p_display_order=>200
,p_column_identifier=>'W'
,p_column_label=>'Native Detail CSV'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000037)
,p_db_column_name=>'NATIVE_ERROR_CSV_LINK'
,p_display_order=>210
,p_column_identifier=>'X'
,p_column_label=>'Native Error CSV'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000038)
,p_db_column_name=>'NATIVE_HTML_SUMMARY_DOWNLOAD_URL'
,p_display_order=>220
,p_column_identifier=>'Y'
,p_column_label=>'Download HTML Summary'
,p_column_link=>'#NATIVE_HTML_SUMMARY_DOWNLOAD_URL#'
,p_column_linktext=>'Open HTML'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000042)
,p_db_column_name=>'NATIVE_SUMMARY_CSV_DOWNLOAD_URL'
,p_display_order=>230
,p_column_identifier=>'AC'
,p_column_label=>'Download Summary CSV'
,p_column_link=>'#NATIVE_SUMMARY_CSV_DOWNLOAD_URL#'
,p_column_linktext=>'Open CSV'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000043)
,p_db_column_name=>'NATIVE_DETAIL_CSV_DOWNLOAD_URL'
,p_display_order=>240
,p_column_identifier=>'AD'
,p_column_label=>'Download Detail CSV'
,p_column_link=>'#NATIVE_DETAIL_CSV_DOWNLOAD_URL#'
,p_column_linktext=>'#NATIVE_DETAIL_CSV_DOWNLOAD_LABEL#'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000046)
,p_db_column_name=>'NATIVE_DETAIL_CSV_DOWNLOAD_LABEL'
,p_display_order=>245
,p_column_identifier=>'AG'
,p_column_label=>'Evidence Action'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000047)
,p_db_column_name=>'NATIVE_BEST_EVIDENCE_DOWNLOAD_URL'
,p_display_order=>246
,p_column_identifier=>'AH'
,p_column_label=>'Best Evidence URL'
,p_column_link=>'#NATIVE_BEST_EVIDENCE_DOWNLOAD_URL#'
,p_column_linktext=>'#NATIVE_BEST_EVIDENCE_DOWNLOAD_LABEL#'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000048)
,p_db_column_name=>'NATIVE_BEST_EVIDENCE_DOWNLOAD_LABEL'
,p_display_order=>247
,p_column_identifier=>'AI'
,p_column_label=>'Best Evidence Action'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000049)
,p_db_column_name=>'NATIVE_BEST_EVIDENCE_DOWNLOAD_TYPE'
,p_display_order=>248
,p_column_identifier=>'AJ'
,p_column_label=>'Best Evidence Type'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000044)
,p_db_column_name=>'NATIVE_ERROR_CSV_DOWNLOAD_URL'
,p_display_order=>250
,p_column_identifier=>'AE'
,p_column_label=>'Download Error CSV'
,p_column_link=>'#NATIVE_ERROR_CSV_DOWNLOAD_URL#'
,p_column_linktext=>'Open Error CSV'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000045)
,p_db_column_name=>'NATIVE_SOURCE_FILE'
,p_display_order=>260
,p_column_identifier=>'AF'
,p_column_label=>'Native Source File'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000039)
,p_db_column_name=>'NATIVE_SOURCE_ROW'
,p_display_order=>270
,p_column_identifier=>'Z'
,p_column_label=>'Native Source Row'
,p_column_type=>'NUMBER'
,p_heading_alignment=>'RIGHT'
,p_column_alignment=>'RIGHT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000040)
,p_db_column_name=>'SCANNER_VERSION'
,p_display_order=>280
,p_column_identifier=>'AA'
,p_column_label=>'Scanner Version'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100200000000041)
,p_db_column_name=>'BENCHMARK_VERSION'
,p_display_order=>290
,p_column_identifier=>'AB'
,p_column_label=>'Benchmark Version'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
,p_use_as_row_header=>'N'
);
wwv_flow_imp_page.create_worksheet_rpt(
 p_id=>wwv_flow_imp.id(100200000000030)
,p_application_user=>'APXWS_DEFAULT'
,p_name=>'Selected Finding'
,p_report_seq=>10
,p_report_alias=>'P20DETAIL'
,p_status=>'PUBLIC'
,p_is_default=>'Y'
,p_display_rows=>10
,p_report_columns=>'FINDING_ID:CONTROL_DISPLAY_ID:RECOMMENDATION_TITLE:CIS_SECTION:CIS_RESULT:CURRENT_STATE:PRIORITY:RISK_SCORE:PRODUCT_DISPLAY_NAME:RESOURCE_TYPE:RESOURCE_NAME:REGION:DUE_STATUS:AGE_DAYS:EVIDENCE_LOCATOR:EVIDENCE_SUMMARY:REMEDIATION:NATIVE_HTML_SUMMARY_DOWNLOAD_URL:NATIVE_SUMMARY_CSV_DOWNLOAD_URL:NATIVE_DETAIL_CSV_DOWNLOAD_URL:NATIVE_DETAIL_CSV_DOWNLOAD_LABEL:NATIVE_BEST_EVIDENCE_DOWNLOAD_URL:NATIVE_BEST_EVIDENCE_DOWNLOAD_LABEL:NATIVE_BEST_EVIDENCE_DOWNLOAD_TYPE:NATIVE_ERROR_CSV_DOWNLOAD_URL:NATIVE_HTML_SUMMARY_LINK:NATIVE_SUMMARY_CSV_LINK:NATIVE_DETAIL_CSV_LINK:NATIVE_ERROR_CSV_LINK:NATIVE_SOURCE_FILE:NATIVE_SOURCE_ROW:SCANNER_VERSION:BENCHMARK_VERSION'
);
end;
/

begin
wwv_flow_imp.import_end(
 p_auto_install_sup_obj => nvl(wwv_flow_application_install.get_auto_install_sup_obj, false)
);
commit;
end;
/
