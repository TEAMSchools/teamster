#!/usr/bin/env bash
# BigQuery Cleanup — generated from bq-cleanup.sql
# Usage:
#   bash .claude/scratch/bq-cleanup.sh              # dry run (default)
#   bash .claude/scratch/bq-cleanup.sh --execute    # actually drop
#   bash .claude/scratch/bq-cleanup.sh --section 2  # only section 2
#   bash .claude/scratch/bq-cleanup.sh --section 3 --execute
set -euo pipefail

PROJECT="teamster-332318"
DRY_RUN=true
SECTION=""

while [[ $# -gt 0 ]]; do
  case "$1" in
  --execute)
    DRY_RUN=false
    shift
    ;;
  --section)
    SECTION="$2"
    shift 2
    ;;
  *)
    echo "Unknown arg: $1"
    exit 1
    ;;
  esac
done

DROPPED=0
SKIPPED=0

run_bq() {
  local cmd="$1"
  if ${DRY_RUN}; then
    echo "[dry-run] ${cmd}"
  else
    echo "[exec] ${cmd}"
    if eval "${cmd}" 2>/dev/null; then
      ((DROPPED++))
    else
      echo "  SKIPPED (already gone or error)"
      ((SKIPPED++))
    fi
  fi
}

drop_table() {
  local fqn="$1" # dataset.table
  run_bq "bq rm -f -t \"${PROJECT}:${fqn}\"" "${fqn}"
}

drop_view() {
  local fqn="$1"
  run_bq "bq rm -f -t \"${PROJECT}:${fqn}\"" "${fqn}"
}

drop_schema() {
  local dataset="$1"
  local flags="${2:--f}" # -f or -r -f (for CASCADE)
  run_bq "bq rm ${flags} \"${PROJECT}:${dataset}\"" "${dataset}"
}

# ---------------------------------------------------------------------------
# Section 1: Empty datasets
# ---------------------------------------------------------------------------
if [[ -z ${SECTION} || ${SECTION} == "1" ]]; then
  echo "=== Section 1: Empty datasets ==="
  drop_schema "cbaldor__dbt_training" "-f"
  drop_schema "kipptaf" "-f"
  drop_schema "kipptaf_accounting" "-f"
  drop_schema "kipptaf_act" "-f"
  drop_schema "kipptaf_hubspot" "-f"
  drop_schema "kipptaf_instagram_business" "-f"
  drop_schema "kipptaf_njdoe" "-f"
  drop_schema "kipptaf_qa" "-f"
  drop_schema "kipptaf_utils" "-f"
  drop_schema "teamster_kipppaterson" "-f"
  echo ""
fi

# ---------------------------------------------------------------------------
# Section 2: True orphans in active dbt datasets
# ---------------------------------------------------------------------------
if [[ -z ${SECTION} || ${SECTION} == "2" ]]; then
  echo "=== Section 2: True orphan tables/views ==="

  # kippcamden_deanslist
  drop_table "kippcamden_deanslist.stg_deanslist__incidents__actions"
  drop_table "kippcamden_deanslist.stg_deanslist__incidents__attachments"
  drop_table "kippcamden_deanslist.stg_deanslist__incidents__custom_fields"
  drop_table "kippcamden_deanslist.stg_deanslist__incidents__penalties"
  drop_table "kippcamden_deanslist.stg_deanslist__students__custom_fields"

  # kippmiami_deanslist
  drop_table "kippmiami_deanslist.stg_deanslist__incidents__actions"
  drop_table "kippmiami_deanslist.stg_deanslist__incidents__attachments"
  drop_table "kippmiami_deanslist.stg_deanslist__incidents__custom_fields"
  drop_table "kippmiami_deanslist.stg_deanslist__incidents__penalties"
  drop_table "kippmiami_deanslist.stg_deanslist__students__custom_fields"

  # kippnewark_deanslist
  drop_table "kippnewark_deanslist.stg_deanslist__incidents__actions"
  drop_table "kippnewark_deanslist.stg_deanslist__incidents__attachments"
  drop_table "kippnewark_deanslist.stg_deanslist__incidents__custom_fields"
  drop_table "kippnewark_deanslist.stg_deanslist__incidents__penalties"
  drop_table "kippnewark_deanslist.stg_deanslist__students__custom_fields"

  # kipptaf_adp_workforce_now
  drop_view "kipptaf_adp_workforce_now.int_adp_workforce_now__employee_memberships_rollup"
  drop_table "kipptaf_adp_workforce_now.stg_adp_workforce_now__workers__work_assignments"
  drop_table "kipptaf_adp_workforce_now.stg_adp_workforce_now__workers__work_assignments__reports_to"

  # kipptaf_amplify
  drop_table "kipptaf_amplify.int_amplify__benchmark_student_summary_unpivot"
  drop_table "kipptaf_amplify.int_amplify__bm_met_criteria"
  drop_table "kipptaf_amplify.stg_amplify__dibels_data_farming"
  drop_table "kipptaf_amplify.stg_amplify__dibels_measures"
  drop_table "kipptaf_amplify.stg_amplify__dibels_pm_expectations"
  drop_table "kipptaf_amplify.stg_amplify__dibels_progress_export"

  # kipptaf_assessments
  drop_table "kipptaf_assessments.stg_assessments__academic_goals"
  drop_table "kipptaf_assessments.stg_assessments__act_scale_score_key"
  drop_table "kipptaf_assessments.stg_assessments__assessment_expectations"
  drop_table "kipptaf_assessments.stg_assessments__course_subject_crosswalk"
  drop_table "kipptaf_assessments.stg_assessments__iready_crosswalk"
  drop_table "kipptaf_assessments.stg_assessments__qbls_power_standards"
  drop_table "kipptaf_assessments.stg_assessments__standard_domains"
  drop_table "kipptaf_assessments.stg_assessments__state_test_comparison"

  # kipptaf_collegeboard
  drop_view "kipptaf_collegeboard.int_collegeboard__psat"
  drop_table "kipptaf_collegeboard.stg_collegeboard__ap_codes"
  drop_table "kipptaf_collegeboard.stg_collegeboard__ap_course_crosswalk"
  drop_table "kipptaf_collegeboard.stg_collegeboard__ap_id_crosswalk"
  drop_table "kipptaf_collegeboard.stg_collegeboard__sat_id_crosswalk"

  # kipptaf_coupa
  drop_table "kipptaf_coupa.stg_coupa__address_name_crosswalk"
  drop_table "kipptaf_coupa.stg_coupa__intacct_department_lookup"
  drop_table "kipptaf_coupa.stg_coupa__intacct_fund_lookup"
  drop_table "kipptaf_coupa.stg_coupa__intacct_location_lookup"
  drop_table "kipptaf_coupa.stg_coupa__intacct_program_lookup"
  drop_table "kipptaf_coupa.stg_coupa__school_name_crosswalk"
  drop_table "kipptaf_coupa.stg_coupa__school_name_lookup"
  drop_table "kipptaf_coupa.stg_coupa__user_exceptions"

  # kipptaf_deanslist
  drop_view "kipptaf_deanslist.stg_deanslist__incidents__actions"
  drop_view "kipptaf_deanslist.stg_deanslist__incidents__attachments"
  drop_view "kipptaf_deanslist.stg_deanslist__incidents__custom_fields"
  drop_view "kipptaf_deanslist.stg_deanslist__incidents__penalties"
  drop_view "kipptaf_deanslist.stg_deanslist__students__custom_fields"

  # kipptaf_extracts
  drop_table "kipptaf_extracts.rpt_appsheet__leadership_development_assignments_fixed"

  # kipptaf_finalsite
  drop_view "kipptaf_finalsite.int_finalsite__status_report"

  # kipptaf_finance
  drop_table "kipptaf_finance.stg_finance__enrollment_targets"
  drop_table "kipptaf_finance.stg_finance__payroll_code_mapping"

  # kipptaf_google_appsheet
  drop_table "kipptaf_google_appsheet.snapshot_seat_tracker__seats_copy"
  drop_table "kipptaf_google_appsheet.snapshot_stipend_and_bonus__output"
  drop_view "kipptaf_google_appsheet.stg_leadership_development__active_users"
  drop_view "kipptaf_google_appsheet.stg_leadership_development__output"
  drop_view "kipptaf_google_appsheet.stg_people__seat_tracker_people"
  drop_view "kipptaf_google_appsheet.stg_seat_tracker__log_archive"
  drop_view "kipptaf_google_appsheet.stg_seat_tracker__seats"
  drop_view "kipptaf_google_appsheet.stg_stipend_and_bonus__output"

  # kipptaf_google_forms
  drop_view "kipptaf_google_forms.int_google_forms__form"
  drop_table "kipptaf_google_forms.stg_google_forms__form__items"
  drop_table "kipptaf_google_forms.stg_google_forms__form_items_extension"
  drop_table "kipptaf_google_forms.stg_google_forms__responses__answers"
  drop_table "kipptaf_google_forms.stg_google_forms__responses__answers__file_upload_answers"
  drop_table "kipptaf_google_forms.stg_google_forms__responses__answers__text_answers"

  # kipptaf_google_sheets
  drop_table "kipptaf_google_sheets.stg_google_sheets__assessments__act_scale_score_key"
  drop_table "kipptaf_google_sheets.stg_google_sheets__assessments__assessment_expectations"
  drop_table "kipptaf_google_sheets.stg_google_sheets__assessments__iready_crosswalk"
  drop_table "kipptaf_google_sheets.stg_google_sheets__finalsite__sample_data"
  drop_table "kipptaf_google_sheets.stg_google_sheets__kippfwd_expected_assessments"
  drop_table "kipptaf_google_sheets.stg_google_sheets__kippfwd_goals"
  drop_table "kipptaf_google_sheets.stg_google_sheets__kippfwd_seasons"

  # kipptaf_iready
  drop_view "kipptaf_iready.base_iready__diagnostic_results"

  # kipptaf_kippadb
  drop_table "kipptaf_kippadb.stg_kippadb__nsc_crosswalk"

  # kipptaf_pearson
  drop_table "kipptaf_pearson.stg_pearson__student_crosswalk"

  # kipptaf_people
  drop_table "kipptaf_people.stg_people__campus_crosswalk"
  drop_table "kipptaf_people.stg_people__location_crosswalk"
  drop_table "kipptaf_people.stg_people__miami_performance_criteria"
  drop_table "kipptaf_people.stg_people__powerschool_crosswalk"
  drop_table "kipptaf_people.stg_people__renewal_approvers"
  drop_table "kipptaf_people.stg_people__renewal_letter_mapping"
  drop_table "kipptaf_people.stg_people__salary_scale"
  drop_table "kipptaf_people.stg_people__staffing_model"

  # kipptaf_performance_management
  drop_table "kipptaf_performance_management.stg_performance_management__leadership_development_metrics"
  drop_table "kipptaf_performance_management.stg_performance_management__teacher_development_observation_details"
  drop_table "kipptaf_performance_management.stg_performance_management__teacher_development_observations"

  # kipptaf_powerschool
  drop_view "kipptaf_powerschool.int_powerschool__assignment_score_rollup"
  drop_view "kipptaf_powerschool.int_powerschool__gpnode"
  drop_view "kipptaf_powerschool.int_powerschool__grad_plan_progress_student"

  # kipptaf_reporting
  drop_table "kipptaf_reporting.stg_reporting__gradebook_expectations"
  drop_table "kipptaf_reporting.stg_reporting__gradebook_flags"
  drop_table "kipptaf_reporting.stg_reporting__graduation_paths_combos"
  drop_table "kipptaf_reporting.stg_reporting__promo_status_cutoffs"
  drop_table "kipptaf_reporting.stg_reporting__terms"

  # kipptaf_schoolmint_grow
  drop_table "kipptaf_schoolmint_grow.stg_schoolmint_grow__assignments__tags"
  drop_table "kipptaf_schoolmint_grow.stg_schoolmint_grow__microgoals"
  drop_table "kipptaf_schoolmint_grow.stg_schoolmint_grow__observations__magic_notes"
  drop_table "kipptaf_schoolmint_grow.stg_schoolmint_grow__observations__observation_scores"
  drop_table "kipptaf_schoolmint_grow.stg_schoolmint_grow__observations__observation_scores__text_boxes"
  drop_table "kipptaf_schoolmint_grow.stg_schoolmint_grow__rubrics"
  drop_table "kipptaf_schoolmint_grow.stg_schoolmint_grow__rubrics__measurement_groups"

  # kipptaf_smartrecruiters
  drop_table "kipptaf_smartrecruiters.stg_smartrecruiters__applicants"

  # kipptaf_students
  drop_view "kipptaf_students.int_students__college_assessment_roster"
  drop_view "kipptaf_students.int_students__finalsite_student_roster"

  # kipptaf_surveys
  drop_table "kipptaf_surveys.stg_surveys__scd_answer_crosswalk"
  drop_table "kipptaf_surveys.stg_surveys__scd_question_crosswalk"

  # kipptaf_tableau
  drop_view "kipptaf_tableau.int_tableau__finalsite_ptg_goals_scaffold"
  drop_view "kipptaf_tableau.int_tableau__finalsite_ptg_school_scaffold"
  drop_view "kipptaf_tableau.int_tableau__gradebook_audit_flags__student"
  drop_view "kipptaf_tableau.int_tableau__gradebook_audit_flags__teacher"
  drop_view "kipptaf_tableau.int_tableau__gradebook_audit_section_week_category_scaffold"
  drop_view "kipptaf_tableau.int_tableau__gradebook_audit_section_week_category_student_scaffold"
  drop_view "kipptaf_tableau.int_tableau__gradebook_audit_section_week_scaffold"
  drop_view "kipptaf_tableau.int_tableau__gradebook_audit_section_week_student_category_scaffold"
  drop_view "kipptaf_tableau.int_tableau__gradebook_audit_section_week_student_scaffold"
  drop_view "kipptaf_tableau.int_tableau__gradebook_audit_teacher_aggs"
  drop_view "kipptaf_tableau.rpt_tableau__athletic_eligibility"
  drop_view "kipptaf_tableau.rpt_tableau__college_assessment_dashboard_v3"
  drop_view "kipptaf_tableau.rpt_tableau__dibels_pm_dashboard"
  drop_view "kipptaf_tableau.rpt_tableau__finalsite_recruitment_enrollment_students_hub_dashboard"
  drop_view "kipptaf_tableau.rpt_tableau__fresh_dashboard_aggregates"
  drop_view "kipptaf_tableau.rpt_tableau__fresh_dashboard_conversions"
  drop_view "kipptaf_tableau.rpt_tableau__fresh_dashboard_detailed"
  drop_view "kipptaf_tableau.rpt_tableau__staff_attrition"
  drop_view "kipptaf_tableau.rpt_tableau__state_assessments_dashboard_cmo_comps"
  drop_view "kipptaf_tableau.rpt_tableau__state_assessments_dashboard_nj_prelim"

  # kipptaf_topline
  drop_view "kipptaf_topline.int_topline__ada_weekly_running"
  drop_view "kipptaf_topline.int_topline__attendance_interventions"
  drop_view "kipptaf_topline.int_topline__iready_diagnostic_weeks"
  drop_view "kipptaf_topline.int_topline__iready_lessons_weeks"
  drop_view "kipptaf_topline.int_topline__retention"
  drop_view "kipptaf_topline.int_topline__seats_staffed_weekly"

  # kipptaf_zendesk
  drop_view "kipptaf_zendesk.base_zendesk__tickets__custom_fields"
  echo ""
fi

# ---------------------------------------------------------------------------
# Section 3: Legacy/removed schema datasets
# ---------------------------------------------------------------------------
if [[ -z ${SECTION} || ${SECTION} == "3" ]]; then
  echo "=== Section 3: Legacy/removed datasets ==="

  # kipptaf_appsheet (stale copies only — 9 BQ-native sources preserved)
  drop_table "kipptaf_appsheet.snapshot_leadership_development__output"
  drop_table "kipptaf_appsheet.snapshot_seat_tracker__seats"
  drop_table "kipptaf_appsheet.snapshot_stipend_and_bonus__output"
  drop_table "kipptaf_appsheet.src_kfwd_career_conversations__output"

  # kipptaf_crdc
  drop_table "kipptaf_crdc.stg_crdc__sced_code_crosswalk"
  drop_table "kipptaf_crdc.stg_crdc__student_numbers"

  # kipptaf_egencia
  drop_table "kipptaf_egencia.stg_egencia__travel_managers"
  drop_table "kipptaf_egencia.stg_egencia__traveler_group_exceptions"
  drop_table "kipptaf_egencia.stg_egencia__traveler_groups"

  # kipptaf_metrics
  drop_table "kipptaf_metrics.kipptaf_time_spine"
  drop_table "kipptaf_metrics.metricflow_time_spine"
  drop_schema "kipptaf_metrics" "-f"
  echo ""
fi

# ---------------------------------------------------------------------------
# Section 4: Legacy ephemeral datasets
# ---------------------------------------------------------------------------
if [[ -z ${SECTION} || ${SECTION} == "4" ]]; then
  echo "=== Section 4: Legacy ephemeral datasets ==="

  datasets=(
    # 4a. z_dev_*
    z_dev_dbt_test__audit
    z_dev_kippcamden_dbt_test__audit z_dev_kippcamden_deanslist z_dev_kippcamden_edplan
    z_dev_kippcamden_extracts z_dev_kippcamden_finalsite z_dev_kippcamden_overgrad
    z_dev_kippcamden_pearson z_dev_kippcamden_powerschool z_dev_kippcamden_titan
    z_dev_kippmiami_dbt_test__audit z_dev_kippmiami_deanslist z_dev_kippmiami_extracts
    z_dev_kippmiami_finalsite z_dev_kippmiami_fldoe z_dev_kippmiami_iready
    z_dev_kippmiami_powerschool z_dev_kippmiami_renlearn
    z_dev_kippnewark_amplify z_dev_kippnewark_dbt_test__audit z_dev_kippnewark_deanslist
    z_dev_kippnewark_edplan z_dev_kippnewark_extracts z_dev_kippnewark_finalsite
    z_dev_kippnewark_iready z_dev_kippnewark_overgrad z_dev_kippnewark_pearson
    z_dev_kippnewark_powerschool z_dev_kippnewark_renlearn z_dev_kippnewark_titan
    z_dev_kippnj_iready z_dev_kippnj_renlearn
    z_dev_kipppaterson z_dev_kipppaterson_amplify z_dev_kipppaterson_dbt_test__audit
    z_dev_kipppaterson_finalsite z_dev_kipppaterson_pearson z_dev_kipppaterson_powerschool
    z_dev_kipptaf z_dev_kipptaf_act z_dev_kipptaf_adp_payroll
    z_dev_kipptaf_adp_workforce_manager z_dev_kipptaf_adp_workforce_now
    z_dev_kipptaf_amplify z_dev_kipptaf_assessments z_dev_kipptaf_collegeboard
    z_dev_kipptaf_coupa z_dev_kipptaf_crdc z_dev_kipptaf_dayforce
    z_dev_kipptaf_dbt_test__audit z_dev_kipptaf_deanslist z_dev_kipptaf_edplan
    z_dev_kipptaf_egencia z_dev_kipptaf_extracts z_dev_kipptaf_finalsite
    z_dev_kipptaf_finance z_dev_kipptaf_fldoe z_dev_kipptaf_google
    z_dev_kipptaf_google_appsheet z_dev_kipptaf_google_directory
    z_dev_kipptaf_google_forms z_dev_kipptaf_google_sheets z_dev_kipptaf_illuminate
    z_dev_kipptaf_iready z_dev_kipptaf_kippadb z_dev_kipptaf_knowbe4
    z_dev_kipptaf_ldap z_dev_kipptaf_marts z_dev_kipptaf_metrics
    z_dev_kipptaf_njdoe z_dev_kipptaf_nsc z_dev_kipptaf_overgrad
    z_dev_kipptaf_pearson z_dev_kipptaf_people z_dev_kipptaf_performance_management
    z_dev_kipptaf_powerschool z_dev_kipptaf_powerschool_enrollment z_dev_kipptaf_qa
    z_dev_kipptaf_renlearn z_dev_kipptaf_reporting z_dev_kipptaf_schoolmint_grow
    z_dev_kipptaf_smartrecruiters z_dev_kipptaf_students z_dev_kipptaf_surveys
    z_dev_kipptaf_tableau z_dev_kipptaf_titan z_dev_kipptaf_topline
    z_dev_kipptaf_utils z_dev_kipptaf_zendesk z_dev_pearson z_dev_powerschool

    # 4b. zz_dbt_*
    zz_dbt_awalters zz_dbt_awalters_adp_payroll zz_dbt_awalters_adp_workforce_manager
    zz_dbt_awalters_adp_workforce_now zz_dbt_awalters_amplify zz_dbt_awalters_assessments
    zz_dbt_awalters_collegeboard zz_dbt_awalters_coupa zz_dbt_awalters_crdc
    zz_dbt_awalters_dayforce zz_dbt_awalters_dbt_test__audit zz_dbt_awalters_deanslist
    zz_dbt_awalters_edplan zz_dbt_awalters_egencia zz_dbt_awalters_extracts
    zz_dbt_awalters_finalsite zz_dbt_awalters_finance zz_dbt_awalters_fldoe
    zz_dbt_awalters_google_appsheet zz_dbt_awalters_google_directory
    zz_dbt_awalters_google_forms zz_dbt_awalters_google_sheets zz_dbt_awalters_illuminate
    zz_dbt_awalters_iready zz_dbt_awalters_kippadb zz_dbt_awalters_knowbe4
    zz_dbt_awalters_ldap zz_dbt_awalters_marts zz_dbt_awalters_metrics
    zz_dbt_awalters_nsc zz_dbt_awalters_overgrad zz_dbt_awalters_pearson
    zz_dbt_awalters_people zz_dbt_awalters_performance_management
    zz_dbt_awalters_powerschool zz_dbt_awalters_powerschool_enrollment
    zz_dbt_awalters_renlearn zz_dbt_awalters_reporting zz_dbt_awalters_schoolmint_grow
    zz_dbt_awalters_smartrecruiters zz_dbt_awalters_students zz_dbt_awalters_surveys
    zz_dbt_awalters_tableau zz_dbt_awalters_titan zz_dbt_awalters_topline
    zz_dbt_awalters_zendesk zz_dbt_cbini_dbt_test__audit zz_dbt_cbini_google_sheets
    zz_dbt_cbini_powerschool

    # 4c. dbt_cgibson_*
    dbt_cgibson_adp_workforce_now dbt_cgibson_amplify dbt_cgibson_assessments
    dbt_cgibson_collegeboard dbt_cgibson_dbt_test__audit dbt_cgibson_deanslist
    dbt_cgibson_edplan dbt_cgibson_extracts dbt_cgibson_finalsite dbt_cgibson_fldoe
    dbt_cgibson_google_forms dbt_cgibson_google_sheets dbt_cgibson_illuminate
    dbt_cgibson_iready dbt_cgibson_kippadb dbt_cgibson_ldap dbt_cgibson_overgrad
    dbt_cgibson_pearson dbt_cgibson_people dbt_cgibson_powerschool dbt_cgibson_students
    dbt_cgibson_surveys dbt_cgibson_tableau dbt_cgibson_titan dbt_cgibson_topline

    # 4d. zz_grangel_*
    zz_grangel_adp_payroll zz_grangel_adp_workforce_manager zz_grangel_adp_workforce_now
    zz_grangel_amplify zz_grangel_assessments zz_grangel_collegeboard zz_grangel_coupa
    zz_grangel_crdc zz_grangel_csgf zz_grangel_dayforce zz_grangel_dbt_test__audit
    zz_grangel_deanslist zz_grangel_edplan zz_grangel_egencia zz_grangel_extracts
    zz_grangel_finalsite zz_grangel_finance zz_grangel_fldoe zz_grangel_google_appsheet
    zz_grangel_google_directory zz_grangel_google_forms zz_grangel_google_sheets
    zz_grangel_illuminate zz_grangel_iready zz_grangel_kippadb zz_grangel_knowbe4
    zz_grangel_ldap zz_grangel_marts zz_grangel_metrics zz_grangel_nsc
    zz_grangel_overgrad zz_grangel_pearson zz_grangel_people
    zz_grangel_performance_management zz_grangel_powerschool
    zz_grangel_powerschool_enrollment zz_grangel_renlearn zz_grangel_reporting
    zz_grangel_schoolmint_grow zz_grangel_smartrecruiters zz_grangel_students
    zz_grangel_surveys zz_grangel_tableau zz_grangel_titan zz_grangel_topline
    zz_grangel_zendesk

    # 4e. zz_cbaldor_*
    zz_cbaldor_adp_payroll zz_cbaldor_adp_workforce_manager zz_cbaldor_adp_workforce_now
    zz_cbaldor_amplify zz_cbaldor_assessments zz_cbaldor_collegeboard zz_cbaldor_coupa
    zz_cbaldor_crdc zz_cbaldor_dayforce zz_cbaldor_dbt_test__audit zz_cbaldor_deanslist
    zz_cbaldor_edplan zz_cbaldor_egencia zz_cbaldor_extracts zz_cbaldor_finalsite
    zz_cbaldor_finance zz_cbaldor_fldoe zz_cbaldor_google_appsheet
    zz_cbaldor_google_directory zz_cbaldor_google_forms zz_cbaldor_google_sheets
    zz_cbaldor_illuminate zz_cbaldor_iready zz_cbaldor_kippadb zz_cbaldor_knowbe4
    zz_cbaldor_ldap zz_cbaldor_marts zz_cbaldor_metrics zz_cbaldor_nsc
    zz_cbaldor_overgrad zz_cbaldor_pearson zz_cbaldor_people
    zz_cbaldor_performance_management zz_cbaldor_powerschool
    zz_cbaldor_powerschool_enrollment zz_cbaldor_renlearn zz_cbaldor_reporting
    zz_cbaldor_schoolmint_grow zz_cbaldor_smartrecruiters zz_cbaldor_students
    zz_cbaldor_surveys zz_cbaldor_tableau zz_cbaldor_titan zz_cbaldor_topline
    zz_cbaldor_zendesk

    # 4f. zz_kverhoff_*
    zz_kverhoff_adp_payroll zz_kverhoff_adp_workforce_manager zz_kverhoff_adp_workforce_now
    zz_kverhoff_amplify zz_kverhoff_assessments zz_kverhoff_collegeboard zz_kverhoff_coupa
    zz_kverhoff_crdc zz_kverhoff_dayforce zz_kverhoff_dbt_test__audit zz_kverhoff_deanslist
    zz_kverhoff_edplan zz_kverhoff_egencia zz_kverhoff_extracts zz_kverhoff_finance
    zz_kverhoff_fldoe zz_kverhoff_google_appsheet zz_kverhoff_google_directory
    zz_kverhoff_google_forms zz_kverhoff_google_sheets zz_kverhoff_illuminate
    zz_kverhoff_iready zz_kverhoff_kippadb zz_kverhoff_knowbe4 zz_kverhoff_ldap
    zz_kverhoff_marts zz_kverhoff_metrics zz_kverhoff_overgrad zz_kverhoff_pearson
    zz_kverhoff_people zz_kverhoff_performance_management zz_kverhoff_powerschool
    zz_kverhoff_powerschool_enrollment zz_kverhoff_renlearn zz_kverhoff_reporting
    zz_kverhoff_schoolmint_grow zz_kverhoff_smartrecruiters zz_kverhoff_students
    zz_kverhoff_surveys zz_kverhoff_tableau zz_kverhoff_titan zz_kverhoff_topline
    zz_kverhoff_zendesk

    # 4g. zz_dev_*
    zz_dev_dbt_test__audit zz_dev_finalsite zz_dev_iready
    zz_dev_kippcamden_deanslist zz_dev_kippcamden_powerschool
    zz_dev_kippmiami_deanslist zz_dev_kippmiami_powerschool
    zz_dev_kippnewark_deanslist zz_dev_kippnewark_powerschool
    zz_dev_kipptaf_google_forms zz_dev_kipptaf_google_sheets
    zz_dev_kipptaf_performance_management zz_dev_kipptaf_schoolmint_grow
    zz_dev_powerschool

    # 4o. Bare user datasets
    zz_cbaldor zz_grangel
  )

  for ds in "${datasets[@]}"; do
    drop_schema "${ds}" "-r -f"
  done
  echo ""
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
if ${DRY_RUN}; then
  echo "DRY RUN complete. Re-run with --execute to apply."
else
  echo "Done. Dropped: ${DROPPED}, Skipped: ${SKIPPED}"
fi
