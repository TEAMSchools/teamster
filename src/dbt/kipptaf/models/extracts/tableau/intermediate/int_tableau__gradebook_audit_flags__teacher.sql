with
    teacher_unpivot_cca as (
        select r.*, f.cte_grouping, f.audit_category, f.code_type,

        from
            {{ ref("int_tableau__gradebook_audit_assignments_teacher") }} unpivot (
                audit_flag_value for audit_flag_name in (
                    w_assign_max_score_not_10,
                    h_assign_max_score_not_10,
                    f_assign_max_score_not_10,
                    s_max_score_greater_100
                )
            ) as r
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on r.academic_year = f.academic_year
            and r.region = f.region
            and r.school_level = f.school_level
            and r.assignment_category_code = f.code
            and r.audit_flag_name = f.audit_flag_name
            and f.cte_grouping = 'class_category_assignment'
        -- permanently remove flags
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e1
            on r.academic_year = e1.academic_year
            and r.region = e1.region
            and r.school_level = e1.school_level
            and r.credit_type = e1.credit_type
            and e1.view_name = 'audit_flags'
            and e1.cte = 'teacher_unpivot_cca'
            and e1.is_quarter_end_date_range is null
        -- temporarily remove flags
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e2
            on r.academic_year = e2.academic_year
            and r.region = e2.region
            and r.course_number = e2.course_number
            and r.audit_flag_name = e2.audit_flag_name
            and r.is_quarter_end_date_range = e2.is_quarter_end_date_range
            and e2.view_name = 'audit_flags'
            and e2.cte = 'teacher_unpivot_cca'
            and e2.is_quarter_end_date_range is not null
        where e1.include_row is null and e2.include_row is null
    ),

    teacher_unpivot_cc as (
        select r.*, f.cte_grouping, f.audit_category, f.code_type,

        from
            {{ ref("int_tableau__gradebook_audit_categories_teacher") }} unpivot (
                audit_flag_value for audit_flag_name in (
                    qt_teacher_s_total_greater_200,
                    qt_teacher_s_total_less_200,
                    qt_teacher_s_total_greater_100,
                    qt_teacher_s_total_less_100,
                    w_expected_assign_count_not_met,
                    h_expected_assign_count_not_met,
                    f_expected_assign_count_not_met,
                    s_expected_assign_count_not_met,
                    w_percent_graded_min_not_met,
                    h_percent_graded_min_not_met,
                    f_percent_graded_min_not_met,
                    s_percent_graded_min_not_met
                )
            ) as r
        inner join
            {{ ref("stg_google_sheets__gradebook_flags") }} as f
            on r.academic_year = f.academic_year
            and r.region = f.region
            and r.school_level = f.school_level
            and r.assignment_category_code = f.code
            and r.audit_flag_name = f.audit_flag_name
            and f.cte_grouping = 'class_category'
        -- permanently remove flags by credit type and gradebook category
        left join
            {{ ref("stg_google_sheets__gradebook_exceptions") }} as e
            on r.academic_year = e.academic_year
            and r.region = e.region
            and r.school_level = e.school_level
            and r.credit_type = e.credit_type
            and r.assignment_category_code = e.gradebook_category
            and e.view_name = 'audit_flags'
            and e.cte = 'teacher_unpivot_cc'
            and e.is_quarter_end_date_range is null
        where e.include_row is null
    )

/* this captures 'class_category_assignment': w_assign_max_score_not_10,
   f_assign_max_score_not_10, h_assign_max_score_not_10, s_max_score_greater_100 */
select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.yearid,
    r.region,
    r.school_level,
    r.schoolid,
    r.school,

    r.hos,
    r.region_school_level,

    r.sectionid,
    r.course_number,

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
    r.teacher_tableau_username,
    r.school_leader,
    r.school_leader_tableau_username,
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
    r.quarter_end_date_insession,
    r.week_number_academic_year,
    r.week_number_quarter,
    r.is_current_week,

    r.section_or_period,
    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.expectation,
    r.notes,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,

    r.assignmentid,
    r.assignment_name,
    r.duedate,
    r.scoretype,
    r.totalpointvalue,

    r.cte_grouping,
    r.audit_flag_name,
    r.n_students,
    r.n_late,
    r.n_exempt,
    r.n_missing,
    r.n_academic_dishonesty,
    r.n_null,
    r.n_is_null_missing,
    r.n_is_null_not_missing,
    r.n_expected,
    r.n_expected_scored,

    null as total_expected_scored_section_quarter_week_category,
    null as total_expected_section_quarter_week_category,
    null as percent_graded_for_quarter_week_class,
    null as sum_totalpointvalue_section_quarter_category,
    null as teacher_running_total_assign_by_cat,

    r.teacher_avg_score_for_assign_per_class_section_and_assign_id,
    r.audit_category,
    r.code_type,

    if(r.audit_flag_value, 1, 0) as audit_flag_value,

from teacher_unpivot_cca as r

union all
-- this captures 'class_category'
select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.yearid,
    r.region,
    r.school_level,
    r.schoolid,
    r.school,

    r.hos,
    r.region_school_level,

    r.sectionid,
    r.course_number,

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
    r.teacher_tableau_username,
    r.school_leader,
    r.school_leader_tableau_username,
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
    r.quarter_end_date_insession,
    r.week_number_academic_year,
    r.week_number_quarter,
    r.is_current_week,

    r.section_or_period,
    r.assignment_category_name,
    r.assignment_category_code,
    r.assignment_category_term,
    r.expectation,
    r.notes,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,
    null as assignmentid,
    null as assignment_name,
    null as duedate,
    null as scoretype,
    null as totalpointvalue,

    r.cte_grouping,
    r.audit_flag_name,

    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_academic_dishonesty,
    null as n_null,
    null as n_is_null_missing,
    null as n_is_null_not_missing,
    null as n_expected,
    null as n_expected_scored,

    r.total_expected_scored_section_quarter_week_category,
    r.total_expected_section_quarter_week_category,
    r.percent_graded_for_quarter_week_class,
    r.sum_totalpointvalue_section_quarter_category,
    r.teacher_running_total_assign_by_cat,

    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    r.audit_category,
    r.code_type,

    if(r.audit_flag_value, 1, 0) as audit_flag_value,

from teacher_unpivot_cc as r
