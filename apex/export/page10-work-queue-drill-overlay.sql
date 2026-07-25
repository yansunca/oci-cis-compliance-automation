prompt --application/page_00010_work_queue_drill_overlay
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
        p_page_id => 10
    );
end;
/

begin
wwv_flow_imp_page.create_page(
 p_id=>10
,p_name=>'Findings Work Queue'
,p_alias=>'FINDINGS-WORK-QUEUE'
,p_step_title=>'Findings Work Queue'
,p_autocomplete_on_off=>'OFF'
,p_page_template_options=>'#DEFAULT#'
,p_protection_level=>'C'
,p_page_component_map=>'18'
);

wwv_flow_imp_page.create_page_plug(
 p_id=>wwv_flow_imp.id(100100000000001)
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
 p_id=>wwv_flow_imp.id(100100000000010)
,p_plug_name=>'Findings Work Queue'
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
'    resource_type,',
'    resource_name,',
'    region,',
'    due_status,',
'    age_days,',
'    last_observed_run_id,',
'    apex_detail_key',
'from oci_cis_app.v_cis_apex_work_queue'))
,p_include_rowid_column=>false
,p_plug_source_type=>'NATIVE_IR'
,p_prn_page_header=>'Findings Work Queue'
);

wwv_flow_imp_page.create_worksheet(
 p_id=>wwv_flow_imp.id(100100000000011)
,p_name=>'Findings Work Queue'
,p_max_row_count_message=>'The maximum row count for this report is #MAX_ROW_COUNT# rows. Please apply a filter to reduce the number of records in your query.'
,p_no_data_found_message=>'No data found.'
,p_pagination_type=>'ROWS_X_TO_Y'
,p_report_list_mode=>'TABS'
,p_lazy_loading=>false
,p_show_detail_link=>'N'
,p_download_formats=>'CSV:HTML:XLSX:PDF'
,p_owner=>'OCI_CIS_APP'
,p_internal_uid=>100100000000011
);

wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100100000000012)
,p_db_column_name=>'FINDING_ID'
,p_display_order=>10
,p_column_identifier=>'A'
,p_column_label=>'Finding'
,p_column_link=>'f?p=&APP_ID.:20:&APP_SESSION.::&DEBUG.::P20_FINDING_ID:#FINDING_ID#'
,p_column_linktext=>'#FINDING_ID#'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100100000000013)
,p_db_column_name=>'CONTROL_DISPLAY_ID'
,p_display_order=>20
,p_column_identifier=>'B'
,p_column_label=>'Control'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100100000000014)
,p_db_column_name=>'CURRENT_STATE'
,p_display_order=>30
,p_column_identifier=>'C'
,p_column_label=>'State'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100100000000015)
,p_db_column_name=>'PRIORITY'
,p_display_order=>40
,p_column_identifier=>'D'
,p_column_label=>'Priority'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100100000000016)
,p_db_column_name=>'RISK_SCORE'
,p_display_order=>50
,p_column_identifier=>'E'
,p_column_label=>'Risk Score'
,p_column_type=>'NUMBER'
,p_heading_alignment=>'RIGHT'
,p_column_alignment=>'RIGHT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100100000000017)
,p_db_column_name=>'PRODUCT_DISPLAY_NAME'
,p_display_order=>60
,p_column_identifier=>'F'
,p_column_label=>'Product'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100100000000018)
,p_db_column_name=>'RESOURCE_TYPE'
,p_display_order=>70
,p_column_identifier=>'G'
,p_column_label=>'Resource Type'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100100000000019)
,p_db_column_name=>'RESOURCE_NAME'
,p_display_order=>80
,p_column_identifier=>'H'
,p_column_label=>'Resource'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100100000000020)
,p_db_column_name=>'REGION'
,p_display_order=>90
,p_column_identifier=>'I'
,p_column_label=>'Region'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100100000000021)
,p_db_column_name=>'DUE_STATUS'
,p_display_order=>100
,p_column_identifier=>'J'
,p_column_label=>'Due Status'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100100000000022)
,p_db_column_name=>'AGE_DAYS'
,p_display_order=>110
,p_column_identifier=>'K'
,p_column_label=>'Age Days'
,p_column_type=>'NUMBER'
,p_heading_alignment=>'RIGHT'
,p_column_alignment=>'RIGHT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100100000000023)
,p_db_column_name=>'LAST_OBSERVED_RUN_ID'
,p_display_order=>120
,p_column_identifier=>'L'
,p_column_label=>'Last Run'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);
wwv_flow_imp_page.create_worksheet_column(
 p_id=>wwv_flow_imp.id(100100000000024)
,p_db_column_name=>'APEX_DETAIL_KEY'
,p_display_order=>130
,p_column_identifier=>'M'
,p_column_label=>'Detail Key'
,p_column_type=>'STRING'
,p_heading_alignment=>'LEFT'
);

wwv_flow_imp_page.create_worksheet_rpt(
 p_id=>wwv_flow_imp.id(100100000000030)
,p_application_user=>'APXWS_DEFAULT'
,p_name=>'Open Work'
,p_report_seq=>10
,p_report_alias=>'P10DRILL'
,p_status=>'PUBLIC'
,p_is_default=>'Y'
,p_display_rows=>25
,p_report_columns=>'FINDING_ID:CONTROL_DISPLAY_ID:CURRENT_STATE:PRIORITY:RISK_SCORE:PRODUCT_DISPLAY_NAME:RESOURCE_TYPE:RESOURCE_NAME:REGION:DUE_STATUS:AGE_DAYS:LAST_OBSERVED_RUN_ID'
,p_sort_column_1=>'PRIORITY'
,p_sort_direction_1=>'ASC'
,p_sort_column_2=>'RISK_SCORE'
,p_sort_direction_2=>'DESC'
,p_sort_column_3=>'AGE_DAYS'
,p_sort_direction_3=>'DESC'
);
wwv_flow_imp_page.create_worksheet_condition(
 p_id=>wwv_flow_imp.id(100100000000040)
,p_report_id=>wwv_flow_imp.id(100100000000030)
,p_name=>'High priority'
,p_condition_type=>'HIGHLIGHT'
,p_allow_delete=>'Y'
,p_column_name=>'PRIORITY'
,p_operator=>'='
,p_expr=>'HIGH'
,p_condition_sql=>'"PRIORITY" = #APXWS_EXPR#'
,p_condition_display=>'Priority = ''HIGH'''
,p_enabled=>'Y'
,p_highlight_sequence=>10
,p_row_bg_color=>'#FFF4CE'
);
wwv_flow_imp_page.create_worksheet_condition(
 p_id=>wwv_flow_imp.id(100100000000041)
,p_report_id=>wwv_flow_imp.id(100100000000030)
,p_name=>'Overdue'
,p_condition_type=>'HIGHLIGHT'
,p_allow_delete=>'Y'
,p_column_name=>'DUE_STATUS'
,p_operator=>'='
,p_expr=>'OVERDUE'
,p_condition_sql=>'"DUE_STATUS" = #APXWS_EXPR#'
,p_condition_display=>'Due Status = ''OVERDUE'''
,p_enabled=>'Y'
,p_highlight_sequence=>20
,p_row_bg_color=>'#FDE7E9'
);
wwv_flow_imp_page.create_worksheet_rpt(
 p_id=>wwv_flow_imp.id(100100000000031)
,p_application_user=>'APXWS_DEFAULT'
,p_name=>'High Priority'
,p_report_seq=>20
,p_report_alias=>'P10HIGH'
,p_status=>'PUBLIC'
,p_is_default=>'N'
,p_display_rows=>25
,p_report_columns=>'FINDING_ID:CONTROL_DISPLAY_ID:CURRENT_STATE:PRIORITY:RISK_SCORE:PRODUCT_DISPLAY_NAME:RESOURCE_TYPE:RESOURCE_NAME:REGION:DUE_STATUS:AGE_DAYS:LAST_OBSERVED_RUN_ID'
,p_sort_column_1=>'RISK_SCORE'
,p_sort_direction_1=>'DESC'
,p_sort_column_2=>'AGE_DAYS'
,p_sort_direction_2=>'DESC'
);
wwv_flow_imp_page.create_worksheet_condition(
 p_id=>wwv_flow_imp.id(100100000000042)
,p_report_id=>wwv_flow_imp.id(100100000000031)
,p_name=>'Priority is high'
,p_condition_type=>'FILTER'
,p_allow_delete=>'Y'
,p_column_name=>'PRIORITY'
,p_operator=>'='
,p_expr=>'HIGH'
,p_condition_sql=>'"PRIORITY" = #APXWS_EXPR#'
,p_condition_display=>'Priority = ''HIGH'''
,p_enabled=>'Y'
);
wwv_flow_imp_page.create_worksheet_rpt(
 p_id=>wwv_flow_imp.id(100100000000032)
,p_application_user=>'APXWS_DEFAULT'
,p_name=>'Native CIS Run'
,p_report_seq=>30
,p_report_alias=>'P10NATIVE'
,p_status=>'PUBLIC'
,p_is_default=>'N'
,p_display_rows=>25
,p_report_columns=>'FINDING_ID:CONTROL_DISPLAY_ID:CURRENT_STATE:PRIORITY:RISK_SCORE:PRODUCT_DISPLAY_NAME:RESOURCE_TYPE:RESOURCE_NAME:REGION:DUE_STATUS:AGE_DAYS:LAST_OBSERVED_RUN_ID'
,p_sort_column_1=>'PRIORITY'
,p_sort_direction_1=>'ASC'
,p_sort_column_2=>'CONTROL_DISPLAY_ID'
,p_sort_direction_2=>'ASC'
);
wwv_flow_imp_page.create_worksheet_condition(
 p_id=>wwv_flow_imp.id(100100000000043)
,p_report_id=>wwv_flow_imp.id(100100000000032)
,p_name=>'Run is FUNC-CIS-MAIN-20260722T073104Z'
,p_condition_type=>'FILTER'
,p_allow_delete=>'Y'
,p_column_name=>'LAST_OBSERVED_RUN_ID'
,p_operator=>'='
,p_expr=>'FUNC-CIS-MAIN-20260722T073104Z'
,p_condition_sql=>'"LAST_OBSERVED_RUN_ID" = #APXWS_EXPR#'
,p_condition_display=>'Last Run = ''FUNC-CIS-MAIN-20260722T073104Z'''
,p_enabled=>'Y'
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
