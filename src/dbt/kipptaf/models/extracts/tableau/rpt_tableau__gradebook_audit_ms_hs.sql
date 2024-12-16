with
    roster_categories as (
        select distinct
            r._dbt_source_relation,
            r.academic_year,
            r.academic_year_display,
            r.region,
            r.school_level,
            r.region_school_level,
            r.schoolid,
            r.school,

            r.studentid,
            r.student_number,
            r.student_name,
            r.grade_level,
            r.salesforce_id,
            r.ktc_cohort,
            r.enroll_status,
            r.cohort,
            r.gender,
            r.ethnicity,
            r.advisory,
            r.hos,
            r.year_in_school,
            r.year_in_network,
            r.rn_undergrad,
            r.is_out_of_district,
            r.is_pathways,
            r.is_retained_year,
            r.is_retained_ever,
            r.lunch_status,
            r.gifted_and_talented,
            r.iep_status,
            r.lep_status,
            r.is_504,
            r.is_counseling_services,
            r.is_student_athlete,
            r.tutoring_nj,
            r.nj_student_tier,
            r.ada,
            r.ada_above_or_at_80,
            r.date_enrolled,

            r.semester,
            r.`quarter`,
            r.week_number,
            r.quarter_start_date,
            r.quarter_end_date,
            r.cal_quarter_end_date,
            r.is_current_quarter,
            r.is_quarter_end_date_range,
            r.audit_start_date,
            r.audit_end_date,
            r.audit_due_date,

            r.assignment_category_name,
            r.assignment_category_code,
            r.assignment_category_term,
            r.expectation,
            r.notes,

            r.section_or_period,
            r.sectionid,
            r.sections_dcid,
            r.section_number,
            r.external_expression,
            r.credit_type,
            r.course_number,
            r.course_name,
            r.exclude_from_gpa,
            r.is_ap_course,

            r.teacher_number,
            r.teacher_name,
            r.tableau_username,

            r.category_quarter_percent_grade,
            r.category_quarter_average_all_courses,

            r.quarter_course_percent_grade_that_matters,
            r.quarter_course_grade_points_that_matters,
            r.quarter_citizenship,
            r.quarter_comment_value,

            f.audit_category,

            t.teacher_assign_id,
            t.teacher_assign_name,
            t.teacher_assign_due_date,
            t.teacher_assign_score_type,
            t.teacher_assign_max_score,
            t.n_students,
            t.n_late,
            t.n_exempt,
            t.n_missing,
            t.n_expected,
            t.n_expected_scored,
            t.teacher_running_total_assign_by_cat,
            t.teacher_avg_score_for_assign_per_class_section_and_assign_id,

        from {{ ref("int_tableau__gradebook_audit_roster") }} as r
        left join
            {{ ref("stg_reporting__gradebook_flags") }} as f
            on r.region = f.region
            and r.school_level = f.school_level
            and r.assignment_category_code = f.code
            and f.cte_grouping not in ('student_course', 'student')
        left join
            {{ ref("int_powerschool__teacher_assignment_audit_base") }} as t
            on r.quarter = t.quarter
            and r.week_number = t.week_number_quarter
            and r.assignment_category_code = t.assignment_category_code
            and r.sectionid = t.sectionid
            and {{ union_dataset_join_clause(left_alias="r", right_alias="t") }}
        where r.school_level != 'ES'
    ),

    roster_quarters as (
        select distinct
            r._dbt_source_relation,
            r.academic_year,
            r.academic_year_display,
            r.region,
            r.school_level,
            r.region_school_level,
            r.schoolid,
            r.school,

            r.studentid,
            r.student_number,
            r.student_name,
            r.grade_level,
            r.salesforce_id,
            r.ktc_cohort,
            r.enroll_status,
            r.cohort,
            r.gender,
            r.ethnicity,
            r.advisory,
            r.hos,
            r.year_in_school,
            r.year_in_network,
            r.rn_undergrad,
            r.is_out_of_district,
            r.is_pathways,
            r.is_retained_year,
            r.is_retained_ever,
            r.lunch_status,
            r.gifted_and_talented,
            r.iep_status,
            r.lep_status,
            r.is_504,
            r.is_counseling_services,
            r.is_student_athlete,
            r.tutoring_nj,
            r.nj_student_tier,
            r.ada,
            r.ada_above_or_at_80,
            r.date_enrolled,

            r.semester,
            r.`quarter`,
            r.week_number,
            r.quarter_start_date,
            r.quarter_end_date,
            r.cal_quarter_end_date,
            r.is_current_quarter,
            r.is_quarter_end_date_range,
            r.audit_start_date,
            r.audit_end_date,
            r.audit_due_date,

            '' as assignment_category_name,
            '' as assignment_category_code,
            '' as assignment_category_term,
            null as expectation,
            '' as notes,

            r.section_or_period,
            r.sectionid,
            r.sections_dcid,
            r.section_number,
            r.external_expression,
            r.credit_type,
            r.course_number,
            r.course_name,
            r.exclude_from_gpa,
            r.is_ap_course,

            r.teacher_number,
            r.teacher_name,
            r.tableau_username,

            null as category_quarter_percent_grade,
            null as category_quarter_average_all_courses,

            r.quarter_course_percent_grade_that_matters,
            r.quarter_course_grade_points_that_matters,
            r.quarter_citizenship,
            r.quarter_comment_value,

            f.audit_category,

        from {{ ref("int_tableau__gradebook_audit_roster") }} as r
        left join
            {{ ref("stg_reporting__gradebook_flags") }} as f
            on r.region = f.region
            and r.school_level = f.school_level
            and r.`quarter` = f.code
            and f.cte_grouping in ('student_course', 'student')
        where r.school_level != 'ES'
    )

select distinct
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    r.studentid,
    r.student_number,
    r.student_name,
    r.grade_level,
    r.salesforce_id,
    r.ktc_cohort,
    r.enroll_status,
    r.cohort,
    r.gender,
    r.ethnicity,
    r.advisory,
    r.hos,
    r.year_in_school,
    r.year_in_network,
    r.rn_undergrad,
    r.is_out_of_district,
    r.is_pathways,
    r.is_retained_year,
    r.is_retained_ever,
    r.lunch_status,
    r.gifted_and_talented,
    r.iep_status,
    r.lep_status,
    r.is_504,
    r.is_counseling_services,
    r.is_student_athlete,
    r.tutoring_nj,
    r.nj_student_tier,
    r.ada,
    r.ada_above_or_at_80,
    r.date_enrolled,

    r.`quarter`,
    r.semester,
    r.week_number,
    r.quarter_start_date,
    r.quarter_end_date,
    r.cal_quarter_end_date,
    r.is_current_quarter,
    r.is_quarter_end_date_range,
    r.audit_start_date,
    r.audit_end_date,
    r.audit_due_date,

    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.expectation,
    r.notes,

    r.section_or_period,
    r.sectionid,
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    r.is_ap_course,

    r.teacher_number,
    r.teacher_name,
    r.tableau_username,

    r.category_quarter_percent_grade,
    r.category_quarter_average_all_courses,

    r.quarter_course_percent_grade_that_matters,
    r.quarter_course_grade_points_that_matters,
    r.quarter_citizenship,
    r.quarter_comment_value,

    r.audit_category,

    r.teacher_assign_id,
    r.teacher_assign_name,
    r.teacher_assign_due_date,
    r.teacher_assign_score_type,
    r.teacher_assign_max_score,
    r.n_students,
    r.n_late,
    r.n_exempt,
    r.n_missing,
    r.n_expected,
    r.n_expected_scored,
    r.teacher_running_total_assign_by_cat,
    r.teacher_avg_score_for_assign_per_class_section_and_assign_id,

    a.raw_score,
    a.score_entered,
    a.assign_final_score_percent,
    a.is_exempt,
    a.is_late,
    a.is_missing,

    a.audit_flag_name,
    a.audit_flag_value,

from roster_categories as r
left join
    {{ ref("int_tableau__gradebook_audit_flags") }} as a
    on r.quarter = a.quarter
    and r.week_number = a.week_number
    and r.teacher_assign_id = a.teacher_assign_id
    and r.assignment_category_code = a.assignment_category_code
    and r.sectionid = a.sectionid
    and r.student_number = a.student_number
    and r.audit_category = a.audit_category
    and {{ union_dataset_join_clause(left_alias="r", right_alias="a") }}
    and a.cte_grouping = 'assignment_student'

union all

select distinct
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    r.studentid,
    r.student_number,
    r.student_name,
    r.grade_level,
    r.salesforce_id,
    r.ktc_cohort,
    r.enroll_status,
    r.cohort,
    r.gender,
    r.ethnicity,
    r.advisory,
    r.hos,
    r.year_in_school,
    r.year_in_network,
    r.rn_undergrad,
    r.is_out_of_district,
    r.is_pathways,
    r.is_retained_year,
    r.is_retained_ever,
    r.lunch_status,
    r.gifted_and_talented,
    r.iep_status,
    r.lep_status,
    r.is_504,
    r.is_counseling_services,
    r.is_student_athlete,
    r.tutoring_nj,
    r.nj_student_tier,
    r.ada,
    r.ada_above_or_at_80,
    r.date_enrolled,

    r.`quarter`,
    r.semester,
    r.week_number,
    r.quarter_start_date,
    r.quarter_end_date,
    r.cal_quarter_end_date,
    r.is_current_quarter,
    r.is_quarter_end_date_range,
    r.audit_start_date,
    r.audit_end_date,
    r.audit_due_date,

    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.expectation,
    r.notes,

    r.section_or_period,
    r.sectionid,
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    r.is_ap_course,

    r.teacher_number,
    r.teacher_name,
    r.tableau_username,

    r.category_quarter_percent_grade,
    r.category_quarter_average_all_courses,

    r.quarter_course_percent_grade_that_matters,
    r.quarter_course_grade_points_that_matters,
    r.quarter_citizenship,
    r.quarter_comment_value,

    r.audit_category,

    null as teacher_assign_id,
    '' as teacher_assign_name,
    cast(null as date) as teacher_assign_due_date,
    '' as teacher_assign_score_type,
    null as teacher_assign_max_score,
    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_expected,
    null as n_expected_scored,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,

    a.audit_flag_name,
    a.audit_flag_value,

from roster_categories as r
left join
    {{ ref("int_tableau__gradebook_audit_flags") }} as a
    on r.quarter = a.quarter
    and r.week_number = a.week_number
    and r.assignment_category_code = a.assignment_category_code
    and r.sectionid = a.sectionid
    and r.student_number = a.student_number
    and r.audit_category = a.audit_category
    and {{ union_dataset_join_clause(left_alias="r", right_alias="a") }}
    and a.audit_flag_name = 'w_grade_inflation'
where r.assignment_category_code = 'W'

union all

select distinct
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    r.studentid,
    r.student_number,
    r.student_name,
    r.grade_level,
    r.salesforce_id,
    r.ktc_cohort,
    r.enroll_status,
    r.cohort,
    r.gender,
    r.ethnicity,
    r.advisory,
    r.hos,
    r.year_in_school,
    r.year_in_network,
    r.rn_undergrad,
    r.is_out_of_district,
    r.is_pathways,
    r.is_retained_year,
    r.is_retained_ever,
    r.lunch_status,
    r.gifted_and_talented,
    r.iep_status,
    r.lep_status,
    r.is_504,
    r.is_counseling_services,
    r.is_student_athlete,
    r.tutoring_nj,
    r.nj_student_tier,
    r.ada,
    r.ada_above_or_at_80,
    r.date_enrolled,

    r.`quarter`,
    r.semester,
    r.week_number,
    r.quarter_start_date,
    r.quarter_end_date,
    r.cal_quarter_end_date,
    r.is_current_quarter,
    r.is_quarter_end_date_range,
    r.audit_start_date,
    r.audit_end_date,
    r.audit_due_date,

    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.expectation,
    r.notes,

    r.section_or_period,
    r.sectionid,
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    r.is_ap_course,

    r.teacher_number,
    r.teacher_name,
    r.tableau_username,

    r.category_quarter_percent_grade,
    r.category_quarter_average_all_courses,

    r.quarter_course_percent_grade_that_matters,
    r.quarter_course_grade_points_that_matters,
    r.quarter_citizenship,
    r.quarter_comment_value,

    r.audit_category,

    null as teacher_assign_id,
    '' as teacher_assign_name,
    cast(null as date) as teacher_assign_due_date,
    '' as teacher_assign_score_type,
    null as teacher_assign_max_score,
    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_expected,
    null as n_expected_scored,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,

    a.audit_flag_name,
    a.audit_flag_value,

from roster_categories as r
left join
    {{ ref("int_tableau__gradebook_audit_flags") }} as a
    on r.quarter = a.quarter
    and r.week_number = a.week_number
    and r.`quarter` = a.`quarter`
    and r.sectionid = a.sectionid
    and r.student_number = a.student_number
    and r.audit_category = a.audit_category
    and {{ union_dataset_join_clause(left_alias="r", right_alias="a") }}
    and a.audit_flag_name = 'qt_effort_grade_missing'
where r.assignment_category_code = 'W'

union all

select distinct
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    r.studentid,
    r.student_number,
    r.student_name,
    r.grade_level,
    r.salesforce_id,
    r.ktc_cohort,
    r.enroll_status,
    r.cohort,
    r.gender,
    r.ethnicity,
    r.advisory,
    r.hos,
    r.year_in_school,
    r.year_in_network,
    r.rn_undergrad,
    r.is_out_of_district,
    r.is_pathways,
    r.is_retained_year,
    r.is_retained_ever,
    r.lunch_status,
    r.gifted_and_talented,
    r.iep_status,
    r.lep_status,
    r.is_504,
    r.is_counseling_services,
    r.is_student_athlete,
    r.tutoring_nj,
    r.nj_student_tier,
    r.ada,
    r.ada_above_or_at_80,
    r.date_enrolled,

    r.`quarter`,
    r.semester,
    r.week_number,
    r.quarter_start_date,
    r.quarter_end_date,
    r.cal_quarter_end_date,
    r.is_current_quarter,
    r.is_quarter_end_date_range,
    r.audit_start_date,
    r.audit_end_date,
    r.audit_due_date,

    '' as assignment_category_name,
    '' as assignment_category_code,
    '' as assignment_category_term,
    null as expectation,
    '' as notes,

    r.section_or_period,
    r.sectionid,
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    r.is_ap_course,

    r.teacher_number,
    r.teacher_name,
    r.tableau_username,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,

    r.quarter_course_percent_grade_that_matters,
    r.quarter_course_grade_points_that_matters,
    r.quarter_citizenship,
    r.quarter_comment_value,

    r.audit_category,

    null as teacher_assign_id,
    '' as teacher_assign_name,
    cast(null as date) as teacher_assign_due_date,
    '' as teacher_assign_score_type,
    null as teacher_assign_max_score,
    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_expected,
    null as n_expected_scored,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,

    a.audit_flag_name,
    a.audit_flag_value,

from roster_quarters as r
left join
    {{ ref("int_tableau__gradebook_audit_flags") }} as a
    on r.quarter = a.quarter
    and r.week_number = a.week_number
    and r.`quarter` = a.`quarter`
    and r.sectionid = a.sectionid
    and r.student_number = a.student_number
    and r.audit_category = a.audit_category
    and {{ union_dataset_join_clause(left_alias="r", right_alias="a") }}
    and a.cte_grouping = 'student_course'

union all

select distinct
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    r.studentid,
    r.student_number,
    r.student_name,
    r.grade_level,
    r.salesforce_id,
    r.ktc_cohort,
    r.enroll_status,
    r.cohort,
    r.gender,
    r.ethnicity,
    r.advisory,
    r.hos,
    r.year_in_school,
    r.year_in_network,
    r.rn_undergrad,
    r.is_out_of_district,
    r.is_pathways,
    r.is_retained_year,
    r.is_retained_ever,
    r.lunch_status,
    r.gifted_and_talented,
    r.iep_status,
    r.lep_status,
    r.is_504,
    r.is_counseling_services,
    r.is_student_athlete,
    r.tutoring_nj,
    r.nj_student_tier,
    r.ada,
    r.ada_above_or_at_80,
    r.date_enrolled,

    r.`quarter`,
    r.semester,
    r.week_number,
    r.quarter_start_date,
    r.quarter_end_date,
    r.cal_quarter_end_date,
    r.is_current_quarter,
    r.is_quarter_end_date_range,
    r.audit_start_date,
    r.audit_end_date,
    r.audit_due_date,

    '' as assignment_category_name,
    '' as assignment_category_code,
    '' as assignment_category_term,
    null as expectation,
    '' as notes,

    r.section_or_period,
    r.sectionid,
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    r.is_ap_course,

    r.teacher_number,
    r.teacher_name,
    r.tableau_username,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,

    r.quarter_course_percent_grade_that_matters,
    r.quarter_course_grade_points_that_matters,
    '' as quarter_citizenship,
    '' as quarter_comment_value,

    r.audit_category,

    null as teacher_assign_id,
    '' as teacher_assign_name,
    cast(null as date) as teacher_assign_due_date,
    '' as teacher_assign_score_type,
    null as teacher_assign_max_score,
    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_expected,
    null as n_expected_scored,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,

    a.audit_flag_name,
    a.audit_flag_value,

from roster_quarters as r
left join
    {{ ref("int_tableau__gradebook_audit_flags") }} as a
    on r.quarter = a.quarter
    and r.week_number = a.week_number
    and r.`quarter` = a.`quarter`
    and r.sectionid = a.sectionid
    and r.student_number = a.student_number
    and r.audit_category = a.audit_category
    and {{ union_dataset_join_clause(left_alias="r", right_alias="a") }}
    and a.cte_grouping = 'student'

union all

select distinct
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    null as studentid,
    null as student_number,
    '' as student_name,
    null as grade_level,
    '' as salesforce_id,
    null as ktc_cohort,
    null as enroll_status,
    null as cohort,
    '' as gender,
    '' as ethnicity,
    '' as advisory,
    '' as hos,
    null as year_in_school,
    null as year_in_network,
    null as rn_undergrad,
    cast(null as boolean) as is_out_of_district,
    cast(null as boolean) as is_pathways,
    cast(null as boolean) as is_retained_year,
    cast(null as boolean) as is_retained_ever,
    '' as lunch_status,
    '' as gifted_and_talented,
    '' as iep_status,
    cast(null as boolean) as lep_status,
    cast(null as boolean) as is_504,
    null as is_counseling_services,
    null as is_student_athlete,
    cast(null as boolean) as tutoring_nj,
    '' as nj_student_tier,
    null as ada,
    cast(null as boolean) as ada_above_or_at_80,
    cast(null as date) as date_enrolled,

    r.`quarter`,
    r.semester,
    r.week_number,
    r.quarter_start_date,
    r.quarter_end_date,
    r.cal_quarter_end_date,
    r.is_current_quarter,
    r.is_quarter_end_date_range,
    r.audit_start_date,
    r.audit_end_date,
    r.audit_due_date,

    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.expectation,
    r.notes,

    r.section_or_period,
    r.sectionid,
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    r.is_ap_course,

    r.teacher_number,
    r.teacher_name,
    r.tableau_username,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,

    null as quarter_course_percent_grade_that_matters,
    null as quarter_course_grade_points_that_matters,
    '' as quarter_citizenship,
    '' as quarter_comment_value,

    r.audit_category,

    r.teacher_assign_id,
    r.teacher_assign_name,
    r.teacher_assign_due_date,
    r.teacher_assign_score_type,
    r.teacher_assign_max_score,
    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_expected,
    null as n_expected_scored,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,

    a.audit_flag_name,
    a.audit_flag_value,

from roster_categories as r
left join
    {{ ref("int_tableau__gradebook_audit_flags") }} as a
    on r.quarter = a.quarter
    and r.week_number = a.week_number
    and r.assignment_category_code = a.assignment_category_code
    and r.teacher_assign_id = a.teacher_assign_id
    and r.sectionid = a.sectionid
    and r.student_number = a.student_number
    and r.audit_category = a.audit_category
    and {{ union_dataset_join_clause(left_alias="r", right_alias="a") }}
    and a.cte_grouping = 'class_category_assignment'

union all

select distinct
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    null as studentid,
    null as student_number,
    '' as student_name,
    null as grade_level,
    '' as salesforce_id,
    null as ktc_cohort,
    null as enroll_status,
    null as cohort,
    '' as gender,
    '' as ethnicity,
    '' as advisory,
    '' as hos,
    null as year_in_school,
    null as year_in_network,
    null as rn_undergrad,
    cast(null as boolean) as is_out_of_district,
    cast(null as boolean) as is_pathways,
    cast(null as boolean) as is_retained_year,
    cast(null as boolean) as is_retained_ever,
    '' as lunch_status,
    '' as gifted_and_talented,
    '' as iep_status,
    cast(null as boolean) as lep_status,
    cast(null as boolean) as is_504,
    null as is_counseling_services,
    null as is_student_athlete,
    cast(null as boolean) as tutoring_nj,
    '' as nj_student_tier,
    null as ada,
    cast(null as boolean) as ada_above_or_at_80,
    cast(null as date) as date_enrolled,

    r.`quarter`,
    r.semester,
    r.week_number,
    r.quarter_start_date,
    r.quarter_end_date,
    r.cal_quarter_end_date,
    r.is_current_quarter,
    r.is_quarter_end_date_range,
    r.audit_start_date,
    r.audit_end_date,
    r.audit_due_date,

    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.expectation,
    r.notes,

    r.section_or_period,
    r.sectionid,
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    r.is_ap_course,

    r.teacher_number,
    r.teacher_name,
    r.tableau_username,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,

    null as quarter_course_percent_grade_that_matters,
    null as quarter_course_grade_points_that_matters,
    '' as quarter_citizenship,
    '' as quarter_comment_value,

    r.audit_category,

    null as teacher_assign_id,
    '' as teacher_assign_name,
    cast(null as date) as teacher_assign_due_date,
    '' as teacher_assign_score_type,
    null as teacher_assign_max_score,
    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_expected,
    null as n_expected_scored,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,

    a.audit_flag_name,
    a.audit_flag_value,

from roster_categories as r
left join
    {{ ref("int_tableau__gradebook_audit_flags") }} as a
    on r.quarter = a.quarter
    and r.week_number = a.week_number
    and r.assignment_category_code = a.assignment_category_code
    and r.sectionid = a.sectionid
    and r.student_number = a.student_number
    and r.audit_category = a.audit_category
    and {{ union_dataset_join_clause(left_alias="r", right_alias="a") }}
    and a.cte_grouping = 'class_category'
