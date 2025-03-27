-- trunk-ignore-all(sqlfluff/AM04)
create or replace table
    kipptaf_appsheet.surveys__scd_question_crosswalk as (
    select *, from kipptaf_surveys.src_surveys__scd_question_crosswalk
);
create or replace table
    kipptaf_appsheet.surveys__scd_answer_crosswalk as (
    select *, from kipptaf_surveys.src_surveys__scd_answer_crosswalk
);
create or replace table
    kipptaf_appsheet.amplify__dibels__pm_expectations as (
    select *, from kipptaf_amplify.src_amplify__dibels_pm_expectations
);
create or replace table
    kipptaf_appsheet.amplify__dibels__measures as (
    select *, from kipptaf_amplify.src_amplify__dibels_measures
);
create or replace table
    kipptaf_appsheet.performance_management__leadership_development_metrics as (
-- trunk-ignore(sqlfluff/LT05)
    select *, from kipptaf_performance_management.src_performance_management__leadership_development_metrics
);
create or replace table
    kipptaf_appsheet.egencia__traveler_groups as (
    select *, from kipptaf_egencia.src_egencia__traveler_groups
);
create or replace table
    kipptaf_appsheet.egencia__travel_managers as (
    select *, from kipptaf_egencia.src_egencia__travel_managers
);
create or replace table
    kipptaf_appsheet.egencia__traveler_group_exceptions as (
    select *, from kipptaf_egencia.src_egencia__traveler_group_exceptions
);
create or replace table
    kipptaf_appsheet.crdc__sced_code_crosswalk as (
    select *, from kipptaf_crdc.src_crdc__sced_code_crosswalk
);
create or replace table
    kipptaf_appsheet.crdc__student_numbers as (
    select *, from kipptaf_crdc.src_crdc__student_numbers
);
create or replace table
    kipptaf_appsheet.coupa__address_name_crosswalk as (
    select *, from kipptaf_coupa.src_coupa__address_name_crosswalk
);
create or replace table
    kipptaf_appsheet.coupa__school_name_crosswalk as (
    select *, from kipptaf_coupa.src_coupa__school_name_crosswalk
);
create or replace table
    kipptaf_appsheet.coupa__school_name_lookup as (
    select *, from kipptaf_coupa.src_coupa__school_name_lookup
);
create or replace table
    kipptaf_appsheet.coupa__user_exceptions as (
    select *, from kipptaf_coupa.src_coupa__user_exceptions
);
create or replace table
    kipptaf_appsheet.coupa__intacct_program_lookup as (
    select *, from kipptaf_coupa.src_coupa__intacct_program_lookup
);
create or replace table
    kipptaf_appsheet.coupa__intacct_location_lookup as (
    select *, from kipptaf_coupa.src_coupa__intacct_location_lookup
);
create or replace table
    kipptaf_appsheet.coupa__intacct_fund_lookup as (
    select *, from kipptaf_coupa.src_coupa__intacct_fund_lookup
);
create or replace table
    kipptaf_appsheet.coupa__intacct_department_lookup as (
    select *, from kipptaf_coupa.src_coupa__intacct_department_lookup
);
create or replace table
    kipptaf_appsheet.assessments__ap_course_crosswalk as (
    select *, from kipptaf_assessments.src_assessments__ap_course_crosswalk
);
create or replace table
    kipptaf_appsheet.assessments__course_subject_crosswalk as (
    select *, from kipptaf_assessments.src_assessments__course_subject_crosswalk
);
create or replace table
    kipptaf_appsheet.assessments__iready_crosswalk as (
    select *, from kipptaf_assessments.src_assessments__iready_crosswalk
);
create or replace table
    kipptaf_appsheet.assessments__academic_goals as (
    select *, from kipptaf_assessments.src_assessments__academic_goals
);
create or replace table
    kipptaf_appsheet.assessments__act_scale_score_key as (
    select *, from kipptaf_assessments.src_assessments__act_scale_score_key
);
create or replace table
    kipptaf_appsheet.assessments__qbls_power_standards as (
    select *, from kipptaf_assessments.src_assessments__qbls_power_standards
);
create or replace table
    kipptaf_appsheet.assessments__standard_domains as (
    select *, from kipptaf_assessments.src_assessments__standard_domains
);
create or replace table
    kipptaf_appsheet.assessments__state_test_comparison as (
    select *, from kipptaf_assessments.src_assessments__state_test_comparison
);
create or replace table
    kipptaf_appsheet.assessments__assessment_expectations as (
    select *, from kipptaf_assessments.src_assessments__assessment_expectations
);
create or replace table
    kipptaf_appsheet.google_forms__form_items_extension as (
    select *, from kipptaf_google_forms.src_google_forms__form_items_extension
);
create or replace table
    kipptaf_appsheet.kippadb__nsc_crosswalk as (
    select *, from kipptaf_kippadb.src_kippadb__nsc_crosswalk
);
create or replace table
    kipptaf_appsheet.reporting__terms as (
    select *, from kipptaf_reporting.src_reporting__terms
);
create or replace table
    kipptaf_appsheet.reporting__gradebook_expectations as (
    select *, from kipptaf_reporting.src_reporting__gradebook_expectations
);
create or replace table
    kipptaf_appsheet.reporting__promo_status_cutoffs as (
    select *, from kipptaf_reporting.src_reporting__promo_status_cutoffs
);
create or replace table
    kipptaf_appsheet.reporting__gradebook_flags as (
    select *, from kipptaf_reporting.src_reporting__gradebook_flags
);
create or replace table
    kipptaf_appsheet.reporting__graduation_path_combos as (
    select *, from kipptaf_reporting.src_reporting__graduation_path_combos
);
create or replace table
    kipptaf_appsheet.collegeboard__id_crosswalk as (
    select *, from kipptaf_collegeboard.src_collegeboard__id_crosswalk
);
create or replace table
    kipptaf_appsheet.people__employee_numbers_archive as (
    select *, from kipptaf_people.src_people__employee_numbers_archive
);
create or replace table
    kipptaf_appsheet.people__location_crosswalk as (
    select *, from kipptaf_people.src_people__location_crosswalk
);
create or replace table
    kipptaf_appsheet.people__campus_crosswalk as (
    select *, from kipptaf_people.src_people__campus_crosswalk
);
create or replace table
    kipptaf_appsheet.people__powerschool_crosswalk as (
    select *, from kipptaf_people.src_people__powerschool_crosswalk
);
create or replace table
    kipptaf_appsheet.people__student_logins_archive as (
    select *, from kipptaf_people.src_people__student_logins_archive
);
create or replace table
    kipptaf_appsheet.people__staffing_model as (
    select *, from kipptaf_people.src_people__staffing_model
);
create or replace table
    kipptaf_appsheet.people__salary_scale as (
    select *, from kipptaf_people.src_people__salary_scale
);
create or replace table
    kipptaf_appsheet.people__miami_performance_criteria as (
    select *, from kipptaf_people.src_people__miami_performance_criteria
);
create or replace table
    kipptaf_appsheet.people__renewal_approvers as (
    select *, from kipptaf_people.src_people__renewal_approvers
);
create or replace table
    kipptaf_appsheet.people__renewal_letter_mapping as (
    select *, from kipptaf_people.src_people__renewal_letter_mapping
);
create or replace table
    kipptaf_appsheet.finance__enrollment_targets as (
    select *, from kipptaf_finance.src_finance__enrollment_targets
);
create or replace table
    kipptaf_appsheet.finance__payroll_code_mapping as (
    select *, from kipptaf_finance.src_finance__payroll_code_mapping
);
