{{- config(materialized="table") -}}

with
    student_unpivot as (
        select
            *,

            case
                when
                    audit_flag_name in (
                        'assign_null_score',
                        'assign_score_above_max',
                        'assign_exempt_with_score',
                        'assign_w_score_less_5',
                        'assign_f_score_less_5',
                        'assign_w_missing_score_not_5',
                        'assign_f_missing_score_not_5',
                        'assign_s_score_less_50p',
                        'assign_s_ms_score_not_conversion_chart_options',
                        'assign_s_hs_score_not_conversion_chart_options'
                    )
                then 'assignment_student'
                when audit_flag_name in ('w_grade_inflation', 'qt_effort_grade_missing')
                then 'student_course_category'
                when
                    audit_flag_name in (
                        'qt_comment_missing',
                        'qt_g1_g8_conduct_code_incorrect',
                        'qt_g1_g8_conduct_code_missing',
                        'qt_grade_70_comment_missing',
                        'qt_kg_conduct_code_incorrect',
                        'qt_kg_conduct_code_missing',
                        'qt_kg_conduct_code_not_hr',
                        'qt_percent_grade_greater_100'
                    )
                then 'student_course'
                when audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2'
                then 'student'
            end as cte_grouping,
        from
            {{ ref("int_tableau__gradebook_audit_assignments_student") }} unpivot (
                audit_flag_value for audit_flag_name in (
                    assign_null_score,
                    assign_score_above_max,
                    assign_exempt_with_score,
                    assign_w_score_less_5,
                    assign_f_score_less_5,
                    assign_w_missing_score_not_5,
                    assign_f_missing_score_not_5,
                    assign_s_score_less_50p,
                    assign_s_ms_score_not_conversion_chart_options,
                    assign_s_hs_score_not_conversion_chart_options,
                    w_grade_inflation,
                    qt_effort_grade_missing,
                    qt_comment_missing,
                    qt_g1_g8_conduct_code_incorrect,
                    qt_g1_g8_conduct_code_missing,
                    qt_grade_70_comment_missing,
                    qt_kg_conduct_code_incorrect,
                    qt_kg_conduct_code_missing,
                    qt_kg_conduct_code_not_hr,
                    qt_percent_grade_greater_100,
                    qt_student_is_ada_80_plus_gpa_less_2
                )
            )
    ),

    teacher_unpivot as (
        select
            *,

            case
                when
                    audit_flag_name in (
                        'w_assign_max_score_not_10',
                        'f_assign_max_score_not_10',
                        's_max_score_greater_100'
                    )
                then 'class_category_assignment'
                when
                    audit_flag_name in (
                        'qt_teacher_s_total_greater_200',
                        'w_expected_assign_count_not_met',
                        'f_expected_assign_count_not_met',
                        's_expected_assign_count_not_met',
                        'w_percent_graded_min_not_met',
                        'f_percent_graded_min_not_met',
                        's_percent_graded_min_not_met'
                    )
                then 'class_category'
            end as cte_grouping,
        from
            {{ ref("int_tableau__gradebook_audit_assignments_teacher") }} unpivot (
                audit_flag_value for audit_flag_name in (
                    w_assign_max_score_not_10,
                    f_assign_max_score_not_10,
                    s_max_score_greater_100,
                    qt_teacher_s_total_greater_200,
                    w_expected_assign_count_not_met,
                    f_expected_assign_count_not_met,
                    s_expected_assign_count_not_met
                )
            )
    ),

    eoq_items as (
        select
            *,

            if(
                audit_flag_name = 'qt_student_is_ada_80_plus_gpa_less_2',
                'student',
                'student_course'
            ) as cte_grouping,

        from
            {{ ref("int_tableau__gradebook_audit_section_week_student_scaffold") }}
            unpivot (
                audit_flag_value for audit_flag_name in (
                    qt_comment_missing,
                    qt_g1_g8_conduct_code_incorrect,
                    qt_g1_g8_conduct_code_missing,
                    qt_grade_70_comment_missing,
                    qt_kg_conduct_code_incorrect,
                    qt_kg_conduct_code_missing,
                    qt_kg_conduct_code_not_hr,
                    qt_percent_grade_greater_100,
                    qt_student_is_ada_80_plus_gpa_less_2
                )
            )
    )

select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.yearid,
    r.region,
    r.school_level,
    r.schoolid,
    r.school,
    r.students_dcid,
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
    r.region_school_level,
    r.year_in_school,
    r.year_in_network,
    r.rn_undergrad,
    r.is_out_of_district,
    r.is_self_contained,
    r.is_retained_year,
    r.is_retained_ever,
    r.lunch_status,
    r.gifted_and_talented,
    r.iep_status,
    r.lep_status,
    r.is_504,
    r.is_counseling_services,
    r.is_student_athlete,
    r.ada,
    r.ada_above_or_at_80,
    r.sectionid,
    r.course_number,
    r.date_enrolled,
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    r.termid,
    r.credit_type,
    r.course_name,
    r.exclude_from_gpa,
    r.teacher_number,
    r.teacher_name,
    r.is_ap_course,
    r.tableau_username,
    r.quarter,
    r.semester,
    r.quarter_start_date,
    r.quarter_end_date,
    r.is_current_term,
    r.is_quarter_end_date_range,
    r.week_start_date,
    r.week_end_date,
    r.week_start_monday,
    r.week_end_sunday,
    r.school_week_start_date_lead,
    r.week_number_academic_year,
    r.week_number_quarter,
    r.quarter_course_percent_grade_that_matters,
    r.quarter_course_grade_points_that_matters,
    r.quarter_citizenship,
    r.quarter_comment_value,
    r.section_or_period,
    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.expectation,
    r.notes,
    r.category_quarter_percent_grade,
    r.category_quarter_average_all_courses,
    r.assignmentid,
    r.assignment_name,
    r.duedate,
    r.scoretype,
    r.totalpointvalue,
    r.category_name,
    r.scorepoints,

    r.actualscoreentered,
    r.is_late,
    r.is_exempt,
    r.is_missing,
    r.score_entered,
    r.assign_final_score_percent,
    r.assign_expected_to_be_scored,
    r.assign_scored,
    r.assign_expected_with_score,
    r.cte_grouping,
    r.audit_flag_name,

    t.n_students,
    t.n_late,
    t.n_exempt,
    t.n_missing,
    t.n_expected,
    t.n_expected_scored,
    t.running_count_assignments_section_category_term,
    t.avg_expected_scored_percent,

    f.audit_category,

    if(r.audit_flag_value, 1, 0) as audit_flag_value,

from student_unpivot as r
inner join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.assignment_category_code = f.code
    and r.audit_flag_name = f.audit_flag_name
    and f.cte_grouping in ('assignment_student', 'student_course_category')
left join
    {{ ref("int_tableau__gradebook_audit_assignments_teacher") }} as t
    on r.region = t.region
    and r.schoolid = t.schoolid
    and r.quarter = t.quarter
    and r.week_number_quarter = t.week_number_quarter
    and r.sectionid = t.sectionid
    and r.assignmentid = t.assignmentid

union all

select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.yearid,
    r.region,
    r.school_level,
    r.schoolid,
    r.school,
    r.students_dcid,
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
    r.region_school_level,
    r.year_in_school,
    r.year_in_network,
    r.rn_undergrad,
    r.is_out_of_district,
    r.is_self_contained,
    r.is_retained_year,
    r.is_retained_ever,
    r.lunch_status,
    r.gifted_and_talented,
    r.iep_status,
    r.lep_status,
    r.is_504,
    r.is_counseling_services,
    r.is_student_athlete,
    r.ada,
    r.ada_above_or_at_80,
    r.sectionid,
    r.course_number,
    r.date_enrolled,
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    r.termid,
    r.credit_type,
    r.course_name,
    r.exclude_from_gpa,
    r.teacher_number,
    r.teacher_name,
    r.is_ap_course,
    r.tableau_username,
    r.quarter,
    r.semester,
    r.quarter_start_date,
    r.quarter_end_date,
    r.is_current_term,
    r.is_quarter_end_date_range,
    r.week_start_date,
    r.week_end_date,
    r.week_start_monday,
    r.week_end_sunday,
    r.school_week_start_date_lead,
    r.week_number_academic_year,
    r.week_number_quarter,
    r.quarter_course_percent_grade_that_matters,
    r.quarter_course_grade_points_that_matters,
    r.quarter_citizenship,
    r.quarter_comment_value,
    r.section_or_period,

    '' as assignment_category_name,
    '' as assignment_category_code,
    '' as assignment_category_term,
    null as expectation,
    '' as notes,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,

    null as assignmentid,
    '' as assignment_name,
    cast(null as date) as duedate,
    '' as scoretype,
    null as totalpointvalue,
    '' as category_name,
    null as scorepoints,

    '' as actualscoreentered,
    null as is_late,
    null as is_exempt,
    null as is_missing,
    null as score_entered,
    null as assign_final_score_percent,
    false as assign_expected_to_be_scored,
    false as assign_scored,
    false as assign_expected_with_score,
    r.cte_grouping,
    r.audit_flag_name,

    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_expected,
    null as n_expected_scored,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    f.audit_category,

    if(r.audit_flag_value, 1, 0) as audit_flag_value,

from eoq_items as r
inner join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.quarter = f.code
    and r.audit_flag_name = f.audit_flag_name
    and f.cte_grouping in ('student_course', 'student')
    and f.audit_category != 'Conduct Code'

union all

select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.yearid,
    r.region,
    r.school_level,
    r.schoolid,
    r.school,
    r.students_dcid,
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
    r.region_school_level,
    r.year_in_school,
    r.year_in_network,
    r.rn_undergrad,
    r.is_out_of_district,
    r.is_self_contained,
    r.is_retained_year,
    r.is_retained_ever,
    r.lunch_status,
    r.gifted_and_talented,
    r.iep_status,
    r.lep_status,
    r.is_504,
    r.is_counseling_services,
    r.is_student_athlete,
    r.ada,
    r.ada_above_or_at_80,
    r.sectionid,
    r.course_number,
    r.date_enrolled,
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    null as termid,
    r.credit_type,
    r.course_name,
    r.exclude_from_gpa,
    r.teacher_number,
    r.teacher_name,
    r.is_ap_course,
    r.tableau_username,
    r.quarter,
    r.semester,
    r.quarter_start_date,
    r.quarter_end_date,
    r.is_current_term,
    r.is_quarter_end_date_range,
    r.week_start_date,
    r.week_end_date,
    r.week_start_monday,
    r.week_end_sunday,
    r.school_week_start_date_lead,
    r.week_number_academic_year,
    r.week_number_quarter,
    r.quarter_course_percent_grade_that_matters,
    r.quarter_course_grade_points_that_matters,
    r.quarter_citizenship,
    r.quarter_comment_value,
    r.section_or_period,

    '' as assignment_category_name,
    '' as assignment_category_code,
    '' as assignment_category_term,
    null as expectation,
    '' as notes,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,

    null as assignmentid,
    '' as assignment_name,
    cast(null as date) as duedate,
    '' as scoretype,
    null as totalpointvalue,
    '' as category_name,
    null as scorepoints,

    '' as actualscoreentered,
    null as is_late,
    null as is_exempt,
    null as is_missing,
    null as score_entered,
    null as assign_final_score_percent,
    false as assign_expected_to_be_scored,
    false as assign_scored,
    false as assign_expected_with_score,
    r.cte_grouping,
    r.audit_flag_name,

    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_expected,
    null as n_expected_scored,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    f.audit_category,

    if(r.audit_flag_value, 1, 0) as audit_flag_value,

from eoq_items as r
inner join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.quarter = f.code
    and r.grade_level = f.grade_level
    and r.audit_flag_name = f.audit_flag_name
    and f.cte_grouping = 'student_course'
    and f.audit_category = 'Conduct Code'

union all

select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.yearid,
    r.region,
    r.school_level,
    r.schoolid,
    r.school,
    null as students_dcid,
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
    r.region_school_level,
    null as year_in_school,
    null as year_in_network,
    null as rn_undergrad,
    false as is_out_of_district,
    false as is_self_contained,
    false as is_retained_year,
    false as is_retained_ever,
    '' as lunch_status,  -- 30
    '' as gifted_and_talented,
    '' as iep_status,
    false as lep_status,  -- 33
    false as is_504,
    null as is_counseling_services,  -- 35
    null as is_student_athlete,
    null as ada,
    false as ada_above_or_at_80,
    r.sectionid,
    r.course_number,
    cast(null as date) as date_enrolled,  -- 41
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    null as termid,
    r.credit_type,
    r.course_name,
    r.exclude_from_gpa,
    r.teacher_number,
    r.teacher_name,  -- 50
    r.is_ap_course,
    r.tableau_username,
    r.quarter,
    r.semester,
    r.quarter_start_date,
    r.quarter_end_date,
    r.is_current_term,
    r.is_quarter_end_date_range,
    r.week_start_date,
    r.week_end_date,  -- 60
    r.week_start_monday,
    r.week_end_sunday,
    r.school_week_start_date_lead,
    r.week_number_academic_year,
    r.week_number_quarter,
    null as quarter_course_percent_grade_that_matters,
    null as quarter_course_grade_points_that_matters,
    '' as quarter_citizenship,
    '' as quarter_comment_value,
    r.section_or_period,  -- 70
    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.expectation,
    r.notes,
    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,  -- 77
    r.assignmentid,  -- 78
    r.assignment_name,
    r.duedate,
    r.scoretype,  -- 81
    r.totalpointvalue,
    '' as category_name,
    null as scorepoints,

    '' as actualscoreentered,
    null as is_late,
    null as is_exempt,
    null as is_missing,
    null as score_entered,
    null as assign_final_score_percent,
    false as assign_expected_to_be_scored,
    false as assign_scored,
    false as assign_expected_with_score,
    r.cte_grouping,
    r.audit_flag_name,

    r.n_students,
    r.n_late,
    r.n_exempt,
    r.n_missing,
    r.n_expected,
    r.n_expected_scored,
    r.running_count_assignments_section_category_term
    as teacher_running_total_assign_by_cat,
    r.avg_expected_scored_percent
    as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    f.audit_category,

    if(r.audit_flag_value, 1, 0) as audit_flag_value,

from teacher_unpivot as r
inner join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.assignment_category_code = f.code
    and r.audit_flag_name = f.audit_flag_name
    and f.cte_grouping = 'class_category_assignment'
    /*
union all

select distinct
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.yearid,
    r.region,
    r.school_level,
    r.schoolid,
    r.school,
    null as students_dcid,
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
    r.region_school_level,
    null as year_in_school,
    null as year_in_network,
    null as rn_undergrad,
    false as is_out_of_district,
    false as is_self_contained,
    false as is_retained_year,
    false as is_retained_ever,
    '' as lunch_status,  -- 30
    '' as gifted_and_talented,
    '' as iep_status,
    false as lep_status,  -- 33
    false as is_504,
    null as is_counseling_services,  -- 35
    null as is_student_athlete,
    null as ada,
    false as ada_above_or_at_80,
    r.sectionid,
    r.course_number,
    cast(null as date) as date_enrolled,  -- 41
    r.sections_dcid,
    r.section_number,
    r.external_expression,
    null as termid,
    r.credit_type,
    r.course_name,
    r.exclude_from_gpa,
    r.teacher_number,
    r.teacher_name,  -- 50
    r.is_ap_course,
    r.tableau_username,
    r.quarter,
    r.semester,
    r.quarter_start_date,
    r.quarter_end_date,
    r.is_current_term,
    r.is_quarter_end_date_range,
    r.week_start_date,
    r.week_end_date,  -- 60
    r.week_start_monday,
    r.week_end_sunday,
    r.school_week_start_date_lead,
    r.week_number_academic_year,
    r.week_number_quarter,
    null as quarter_course_percent_grade_that_matters,
    null as quarter_course_grade_points_that_matters,
    '' as quarter_citizenship,
    '' as quarter_comment_value,
    r.section_or_period,  -- 70
    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.expectation,
    r.notes,
    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,  -- 77
    r.assignmentid,  -- 78
    r.assignment_name,
    r.duedate,
    r.scoretype,  -- 81
    r.totalpointvalue,
    '' as category_name,
    null as scorepoints,

    '' as actualscoreentered,
    null as is_late,
    null as is_exempt,
    null as is_missing,
    null as score_entered,
    null as assign_final_score_percent,
    false as assign_expected_to_be_scored,
    false as assign_scored,
    false as assign_expected_with_score,
    r.cte_grouping,
    r.audit_flag_name,

    r.n_students,
    r.n_late,
    r.n_exempt,
    r.n_missing,
    r.n_expected,
    r.n_expected_scored,
    r.running_count_assignments_section_category_term
    as teacher_running_total_assign_by_cat,
    r.avg_expected_scored_percent
    as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    f.audit_category,

    if(r.audit_flag_value, 1, 0) as audit_flag_value,

from teacher_unpivot as r
inner join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.assignment_category_code = f.code
    and r.audit_flag_name = f.audit_flag_name
    and f.cte_grouping in ('class_category', 'class_category_assignment')*/
    
