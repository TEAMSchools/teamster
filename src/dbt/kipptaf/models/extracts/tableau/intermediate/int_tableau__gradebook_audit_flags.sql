{{- config(materialized="table") -}}

with
    assignment_student as (
        select
            f._dbt_source_relation,
            f.academic_year,
            f.academic_year_display,
            f.region,
            f.school_level,
            f.region_school_level,
            f.schoolid,
            f.school,

            f.student_number,
            f.grade_level,
            f.date_enrolled,

            f.semester,
            f.`quarter`,
            f.week_number,
            f.quarter_start_date,
            f.quarter_end_date,
            f.cal_quarter_end_date,
            f.is_current_quarter,
            f.is_quarter_end_date_range,
            f.audit_start_date,
            f.audit_end_date,
            f.audit_due_date,

            f.assignment_category_name,
            f.assignment_category_code,
            f.assignment_category_term,
            f.sectionid,
            f.credit_type,
            f.course_number,
            f.course_name,
            f.exclude_from_gpa,
            f.is_ap_course,

            f.teacher_number,
            f.teacher_name,

            t.teacher_assign_id,
            t.teacher_assign_due_date,

            s.raw_score,
            s.score_entered,
            s.assign_final_score_percent,
            s.is_exempt,
            s.is_late,
            s.is_missing,

            s.assign_null_score,
            s.assign_score_above_max,
            s.assign_exempt_with_score,
            s.assign_w_score_less_5,
            s.assign_f_score_less_5,
            s.assign_w_missing_score_not_5,
            s.assign_f_missing_score_not_5,
            s.assign_s_score_less_50p,
            s.assign_s_ms_score_not_conversion_chart_options,
            s.assign_s_hs_score_not_conversion_chart_options,

            'assignment_student' as cte_grouping,

        from {{ ref("int_tableau__gradebook_audit_roster") }} as f
        inner join
            {{ ref("int_powerschool__teacher_assignment_audit") }} as t
            on f.sectionid = t.sectionid
            and f.quarter = t.quarter
            and f.week_number = t.week_number_quarter
            and f.assignment_category_code = t.assignment_category_code
            and {{ union_dataset_join_clause(left_alias="f", right_alias="t") }}
        inner join
            {{ ref("int_powerschool__student_assignment_audit") }} as s
            on f.studentid = s.studentid
            and f.sectionid = s.sectionid
            and f.quarter = s.quarter
            and {{ union_dataset_join_clause(left_alias="f", right_alias="s") }}
            and t.week_number_quarter = s.week_number_quarter
            and t.teacher_assign_id = s.assignmentid
            and t.assignment_category_code = s.assignment_category_code
            and {{ union_dataset_join_clause(left_alias="t", right_alias="s") }}
    ),

    student_course_category_inflation as (
        select
            _dbt_source_relation,
            academic_year,
            academic_year_display,
            region,
            school_level,
            region_school_level,
            schoolid,
            school,

            student_number,
            grade_level,

            semester,
            `quarter`,
            week_number,
            quarter_start_date,
            quarter_end_date,
            cal_quarter_end_date,
            is_current_quarter,
            is_quarter_end_date_range,
            audit_start_date,
            audit_end_date,
            audit_due_date,

            assignment_category_name,
            assignment_category_code,
            assignment_category_term,
            sectionid,
            credit_type,
            course_number,
            course_name,
            exclude_from_gpa,

            teacher_number,
            teacher_name,
            category_quarter_percent_grade,
            category_quarter_average_all_courses,

            'student_course_category' as cte_grouping,

            if(
                assignment_category_code = 'W'
                and grade_level > 4
                and abs(
                    round(category_quarter_average_all_courses, 2)
                    - round(category_quarter_percent_grade, 2)
                )
                >= 30,
                true,
                false
            ) as w_grade_inflation,

        from {{ ref("int_tableau__gradebook_audit_roster") }}
        where assignment_category_code = 'W' and school_level != 'ES'
    ),

    student_course_category_effort as (
        select
            _dbt_source_relation,
            academic_year,
            academic_year_display,
            region,
            school_level,
            region_school_level,
            schoolid,
            school,

            student_number,
            grade_level,

            semester,
            `quarter`,
            week_number,
            quarter_start_date,
            quarter_end_date,
            cal_quarter_end_date,
            is_current_quarter,
            is_quarter_end_date_range,
            audit_start_date,
            audit_end_date,
            audit_due_date,

            assignment_category_name,
            assignment_category_code,
            assignment_category_term,
            sectionid,
            credit_type,
            course_number,
            course_name,
            exclude_from_gpa,

            teacher_number,
            teacher_name,
            category_quarter_percent_grade,
            category_quarter_average_all_courses,

            'student_course_category' as cte_grouping,

            if(
                category_quarter_percent_grade is null and is_quarter_end_date_range,
                true,
                false
            ) as qt_effort_grade_missing,

        from {{ ref("int_tableau__gradebook_audit_roster") }}
        where region = 'Miami' and assignment_category_code = 'W'
    ),

    student_course_nj_ms_hs as (
        -- note for charlie if this is moved out of int_tableau: i dont have a way to
        -- dedup this otherwise because the FROM table uses categories, and for this
        -- flag tagging, categories are not used, just the course rows themselves.
        -- open to suggestions on how to dedup without distinct, tho!
        select distinct
            _dbt_source_relation,
            academic_year,
            academic_year_display,
            region,
            school_level,
            region_school_level,
            schoolid,
            school,

            student_number,
            grade_level,

            semester,
            `quarter`,
            week_number,
            quarter_start_date,
            quarter_end_date,
            cal_quarter_end_date,
            is_current_quarter,
            is_quarter_end_date_range,
            audit_start_date,
            audit_end_date,
            audit_due_date,

            sectionid,
            credit_type,
            course_number,
            course_name,
            exclude_from_gpa,

            teacher_number,
            teacher_name,
            quarter_course_percent_grade_that_matters,
            quarter_comment_value,

            'student_course' as cte_grouping,

            if(
                quarter_course_percent_grade_that_matters > 100, true, false
            ) as qt_percent_grade_greater_100,

            if(
                is_quarter_end_date_range
                and quarter_course_percent_grade_that_matters < 70
                and quarter_comment_value is null,
                true,
                false
            ) as qt_grade_70_comment_missing,

        from {{ ref("int_tableau__gradebook_audit_roster") }}
        where region != 'Miami' and school_level != 'ES'
    ),

    student_course_fl_ms as (
        -- note for charlie if this is moved out of int_tableau: i dont have a way to
        -- dedup this otherwise because the FROM table uses categories, and for this
        -- flag tagging, categories are not used, just the course rows themselves.
        -- open to suggestions on how to dedup without distinct, tho!
        select distinct
            _dbt_source_relation,
            academic_year,
            academic_year_display,
            region,
            school_level,
            region_school_level,
            schoolid,
            school,

            student_number,
            grade_level,

            semester,
            `quarter`,
            week_number,
            quarter_start_date,
            quarter_end_date,
            cal_quarter_end_date,
            is_current_quarter,
            is_quarter_end_date_range,
            audit_start_date,
            audit_end_date,
            audit_due_date,

            sectionid,
            credit_type,
            course_number,
            course_name,
            exclude_from_gpa,

            teacher_number,
            teacher_name,
            quarter_course_percent_grade_that_matters,
            quarter_citizenship,
            quarter_comment_value,

            'student_course' as cte_grouping,

            if(
                quarter_course_percent_grade_that_matters > 100, true, false
            ) as qt_percent_grade_greater_100,

            if(
                is_quarter_end_date_range
                and quarter_course_percent_grade_that_matters < 70
                and quarter_comment_value is null,
                true,
                false
            ) as qt_grade_70_comment_missing,

            if(
                is_quarter_end_date_range
                and course_name != 'HR'
                and quarter_citizenship is null,
                true,
                false
            ) as qt_g1_g8_conduct_code_missing,

            if(
                is_quarter_end_date_range
                and course_name != 'HR'
                and quarter_citizenship is not null
                and quarter_citizenship not in ('A', 'B', 'C', 'D', 'E', 'F'),
                true,
                false
            ) as qt_g1_g8_conduct_code_incorrect,

        from {{ ref("int_tableau__gradebook_audit_roster") }}
        where region = 'Miami' and school_level != 'ES'
    ),

    student_course_fl_es as (
        -- note for charlie if this is moved out of int_tableau: i dont have a way to
        -- dedup this otherwise because the FROM table uses categories, and for this
        -- flag tagging, categories are not used, just the course rows themselves.
        -- open to suggestions on how to dedup without distinct, tho!
        select distinct
            _dbt_source_relation,
            academic_year,
            academic_year_display,
            region,
            school_level,
            region_school_level,
            schoolid,
            school,

            student_number,
            grade_level,

            semester,
            `quarter`,
            week_number,
            quarter_start_date,
            quarter_end_date,
            cal_quarter_end_date,
            is_current_quarter,
            is_quarter_end_date_range,
            audit_start_date,
            audit_end_date,
            audit_due_date,

            sectionid,
            credit_type,
            course_number,
            course_name,
            exclude_from_gpa,

            teacher_number,
            teacher_name,
            quarter_course_percent_grade_that_matters,
            quarter_citizenship,
            quarter_comment_value,

            'student_course' as cte_grouping,

            case
                when not is_quarter_end_date_range
                then false
                when
                    grade_level = 0
                    and course_name = 'HR'
                    and quarter_citizenship is null
                then true
                else false
            end as qt_kg_conduct_code_missing,

            if(
                is_quarter_end_date_range
                and grade_level = 0
                and course_name != 'HR'
                and quarter_citizenship is not null,
                true,
                false
            ) as qt_kg_conduct_code_not_hr,

            if(
                is_quarter_end_date_range
                and grade_level = 0
                and course_name = 'HR'
                and quarter_citizenship is not null
                and quarter_citizenship not in ('E', 'G', 'S', 'M'),
                true,
                false
            ) as qt_kg_conduct_code_incorrect,

            if(
                quarter_course_percent_grade_that_matters > 100, true, false
            ) as qt_percent_grade_greater_100,

            if(
                is_quarter_end_date_range and quarter_comment_value is null, true, false
            ) as qt_comment_missing,

            if(
                is_quarter_end_date_range
                and grade_level != 0
                and course_name != 'HR'
                and quarter_citizenship is null,
                true,
                false
            ) as qt_g1_g8_conduct_code_missing,

            if(
                is_quarter_end_date_range
                and grade_level != 0
                and course_name != 'HR'
                and quarter_citizenship is not null
                and quarter_citizenship not in ('A', 'B', 'C', 'D', 'E', 'F'),
                true,
                false
            ) as qt_g1_g8_conduct_code_incorrect,

        from {{ ref("int_tableau__gradebook_audit_roster") }}
        where region = 'Miami' and school_level = 'ES'
    ),

    student as (
        -- note for charlie if this is moved out of int_tableau: i dont have a way to
        -- dedup this otherwise because the FROM table uses categories, and for this
        -- flag tagging, categories are not used, just the course rows themselves.
        -- open to suggestions on how to dedup without distinct, tho!
        select distinct
            _dbt_source_relation,
            academic_year,
            academic_year_display,
            region,
            school_level,
            region_school_level,
            schoolid,
            school,

            student_number,
            grade_level,
            ada_above_or_at_80,

            semester,
            `quarter`,
            week_number,
            quarter_start_date,
            quarter_end_date,
            cal_quarter_end_date,
            is_current_quarter,
            is_quarter_end_date_range,
            audit_start_date,
            audit_end_date,
            audit_due_date,

            sectionid,
            credit_type,
            course_number,
            course_name,
            exclude_from_gpa,

            teacher_number,
            teacher_name,
            quarter_course_percent_grade_that_matters,
            quarter_course_grade_points_that_matters,

            'student' as cte_grouping,

            if(
                ada_above_or_at_80 and quarter_course_grade_points_that_matters < 2.0,
                true,
                false
            ) as qt_student_is_ada_80_plus_gpa_less_2,

        from {{ ref("int_tableau__gradebook_audit_roster") }}
        where school_level != 'ES'
    ),

    class_category_assignment as (
        -- note for charlie if this is moved out of int_tableau: need the distinct
        -- because the FROM table has student-level data but for this i need it at the
        -- teacher level
        select distinct
            f._dbt_source_relation,
            f.academic_year,
            f.academic_year_display,
            f.region,
            f.school_level,
            f.region_school_level,
            f.schoolid,
            f.school,

            f.semester,
            f.`quarter`,
            f.week_number,
            f.quarter_start_date,
            f.quarter_end_date,
            f.cal_quarter_end_date,
            f.is_current_quarter,
            f.is_quarter_end_date_range,
            audit_start_date,
            audit_end_date,
            f.audit_due_date,

            f.assignment_category_name,
            f.assignment_category_code,
            f.assignment_category_term,
            f.sectionid,
            f.credit_type,
            f.course_number,
            f.course_name,
            f.exclude_from_gpa,

            f.teacher_number,
            f.teacher_name,

            t.teacher_assign_id,
            t.w_assign_max_score_not_10,
            t.f_assign_max_score_not_10,
            t.s_max_score_greater_100,

            'class_category_assignment' as cte_grouping,

        from {{ ref("int_tableau__gradebook_audit_roster") }} as f
        inner join
            {{ ref("int_powerschool__teacher_assignment_audit") }} as t
            on f.sectionid = t.sectionid
            and f.quarter = t.quarter
            and f.week_number = t.week_number_quarter
            and f.assignment_category_code = t.assignment_category_code
            and {{ union_dataset_join_clause(left_alias="f", right_alias="t") }}
    ),

    class_category as (
        -- note for charlie if this is moved out of int_tableau: need the distinct
        -- because the FROM table has student-level data but for this i need it at the
        -- teacher level
        select distinct
            f._dbt_source_relation,
            f.academic_year,
            f.academic_year_display,
            f.region,
            f.school_level,
            f.region_school_level,
            f.schoolid,
            f.school,

            f.semester,
            f.`quarter`,
            f.week_number,
            f.quarter_start_date,
            f.quarter_end_date,
            f.cal_quarter_end_date,
            f.is_current_quarter,
            f.is_quarter_end_date_range,
            f.audit_start_date,
            f.audit_end_date,
            f.audit_due_date,

            f.assignment_category_name,
            f.assignment_category_code,
            f.assignment_category_term,
            f.sectionid,
            f.credit_type,
            f.course_number,
            f.course_name,
            f.exclude_from_gpa,

            f.teacher_number,
            f.teacher_name,

            t.qt_teacher_s_total_greater_200,
            t.w_expected_assign_count_not_met,
            t.f_expected_assign_count_not_met,
            t.s_expected_assign_count_not_met,

            'class_category' as cte_grouping,

        from {{ ref("int_tableau__gradebook_audit_roster") }} as f
        inner join
            {{ ref("int_powerschool__teacher_assignment_audit") }} as t
            on f.sectionid = t.sectionid
            and f.quarter = t.quarter
            and f.week_number = t.week_number_quarter
            and f.assignment_category_code = t.assignment_category_code
            and {{ union_dataset_join_clause(left_alias="f", right_alias="t") }}
    )

select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    r.student_number,
    r.grade_level,
    null as ada,
    null as ada_above_or_at_80,
    date_enrolled,

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
    r.sectionid,
    null as sections_dcid,
    null as section_number,
    '' as external_expression,
    null as section_or_period,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    r.is_ap_course,

    r.teacher_number,
    r.teacher_name,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,
    null as quarter_course_percent_grade_that_matters,
    null as quarter_course_grade_points_that_matters,
    '' as quarter_citizenship,
    '' as quarter_comment_value,

    r.teacher_assign_id,
    '' as teacher_assign_name,
    r.teacher_assign_due_date,
    '' as teacher_assign_score_type,
    null as teacher_assign_max_score,
    null as n_students,
    null as n_late,
    null as n_exempt,
    null as n_missing,
    null as n_expected,
    null as n_expected_scored,
    null as teacher_assign_count,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    r.raw_score,
    r.score_entered,
    r.assign_final_score_percent,
    r.is_exempt,
    r.is_late,
    r.is_missing,
    r.cte_grouping,

    r.audit_flag_name,

    f.audit_category,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from
    assignment_student unpivot (
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
            assign_s_hs_score_not_conversion_chart_options
        )
    ) as r
left join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.assignment_category_code = f.code
    and r.audit_flag_name = f.audit_flag_name
where audit_flag_value

union all

select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    r.student_number,
    r.grade_level,
    null as ada,
    null as ada_above_or_at_80,
    cast(null as date) as date_enrolled,

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
    r.sectionid,
    null as sections_dcid,
    null as section_number,
    '' as external_expression,
    null as section_or_period,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    null as is_ap_course,

    r.teacher_number,
    r.teacher_name,

    r.category_quarter_percent_grade,
    r.category_quarter_average_all_courses,
    null as quarter_course_percent_grade_that_matters,
    null as quarter_course_grade_points_that_matters,
    '' as quarter_citizenship,
    '' as quarter_comment_value,

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
    null as teacher_assign_count,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,
    r.cte_grouping,

    r.audit_flag_name,

    f.audit_category,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from
    student_course_category_inflation
    unpivot (audit_flag_value for audit_flag_name in (w_grade_inflation)) as r
left join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.assignment_category_code = f.code
    and r.audit_flag_name = f.audit_flag_name
where audit_flag_value

union all

select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    r.student_number,
    r.grade_level,
    null as ada,
    null as ada_above_or_at_80,
    cast(null as date) as date_enrolled,

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
    r.sectionid,
    null as sections_dcid,
    null as section_number,
    '' as external_expression,
    null as section_or_period,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    null as is_ap_course,

    r.teacher_number,
    r.teacher_name,

    r.category_quarter_percent_grade,
    r.category_quarter_average_all_courses,
    null as quarter_course_percent_grade_that_matters,
    null as quarter_course_grade_points_that_matters,
    '' as quarter_citizenship,
    '' as quarter_comment_value,

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
    null as teacher_assign_count,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,
    r.cte_grouping,

    r.audit_flag_name,

    f.audit_category,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from
    student_course_category_effort
    unpivot (audit_flag_value for audit_flag_name in (qt_effort_grade_missing)) as r
left join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.assignment_category_code = f.code
    and r.audit_flag_name = f.audit_flag_name
where audit_flag_value

union all

select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    r.student_number,
    r.grade_level,
    null as ada,
    null as ada_above_or_at_80,
    cast(null as date) as date_enrolled,

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

    null as assignment_category_name,
    null as assignment_category_code,
    null as assignment_category_term,
    r.sectionid,
    null as sections_dcid,
    null as section_number,
    '' as external_expression,
    null as section_or_period,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    null as is_ap_course,

    r.teacher_number,
    r.teacher_name,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,
    r.quarter_course_percent_grade_that_matters,
    null as quarter_course_grade_points_that_matters,
    '' as quarter_citizenship,
    r.quarter_comment_value,

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
    null as teacher_assign_count,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,
    r.cte_grouping,

    r.audit_flag_name,

    f.audit_category,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from
    student_course_nj_ms_hs unpivot (
        audit_flag_value for audit_flag_name
        in (qt_percent_grade_greater_100, qt_grade_70_comment_missing)
    ) as r
left join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.`quarter` = f.code
    and r.audit_flag_name = f.audit_flag_name
where audit_flag_value

union all

select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    r.student_number,
    r.grade_level,
    null as ada,
    null as ada_above_or_at_80,
    cast(null as date) as date_enrolled,

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

    null as assignment_category_name,
    null as assignment_category_code,
    null as assignment_category_term,
    r.sectionid,
    null as sections_dcid,
    null as section_number,
    '' as external_expression,
    null as section_or_period,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    null as is_ap_course,

    r.teacher_number,
    r.teacher_name,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,
    r.quarter_course_percent_grade_that_matters,
    null as quarter_course_grade_points_that_matters,
    r.quarter_citizenship,
    r.quarter_comment_value,

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
    null as teacher_assign_count,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,
    r.cte_grouping,

    r.audit_flag_name,

    f.audit_category,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from
    student_course_fl_ms unpivot (
        audit_flag_value for audit_flag_name in (
            qt_percent_grade_greater_100,
            qt_grade_70_comment_missing,
            qt_g1_g8_conduct_code_missing,
            qt_g1_g8_conduct_code_incorrect
        )
    ) as r
left join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.`quarter` = f.code
    and r.audit_flag_name = f.audit_flag_name
where audit_flag_value

union all

select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    r.student_number,
    r.grade_level,
    null as ada,
    null as ada_above_or_at_80,
    cast(null as date) as date_enrolled,

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

    null as assignment_category_name,
    null as assignment_category_code,
    null as assignment_category_term,
    r.sectionid,
    null as sections_dcid,
    null as section_number,
    '' as external_expression,
    null as section_or_period,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    null as is_ap_course,

    r.teacher_number,
    r.teacher_name,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,
    r.quarter_course_percent_grade_that_matters,
    null as quarter_course_grade_points_that_matters,
    r.quarter_citizenship,
    r.quarter_comment_value,

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
    null as teacher_assign_count,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,
    r.cte_grouping,

    r.audit_flag_name,

    f.audit_category,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from
    student_course_fl_es unpivot (
        audit_flag_value for audit_flag_name in (
            qt_percent_grade_greater_100,
            qt_comment_missing,
            qt_g1_g8_conduct_code_missing,
            qt_g1_g8_conduct_code_incorrect,
            qt_kg_conduct_code_missing,
            qt_kg_conduct_code_not_hr,
            qt_kg_conduct_code_incorrect
        )
    ) as r
left join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.`quarter` = f.code
    and r.audit_flag_name = f.audit_flag_name
where audit_flag_value

union all

select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    r.student_number,
    r.grade_level,
    null as ada,
    r.ada_above_or_at_80,
    cast(null as date) as date_enrolled,

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

    null as assignment_category_name,
    null as assignment_category_code,
    null as assignment_category_term,
    r.sectionid,
    null as sections_dcid,
    null as section_number,
    '' as external_expression,
    null as section_or_period,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    null as is_ap_course,

    r.teacher_number,
    r.teacher_name,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,
    r.quarter_course_percent_grade_that_matters,
    r.quarter_course_grade_points_that_matters,
    null as quarter_citizenship,
    null as quarter_comment_value,

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
    null as teacher_assign_count,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,
    r.cte_grouping,

    r.audit_flag_name,

    f.audit_category,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from
    student unpivot (
        audit_flag_value for audit_flag_name in (qt_student_is_ada_80_plus_gpa_less_2)
    ) as r
left join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.`quarter` = f.code
    and r.audit_flag_name = f.audit_flag_name
where audit_flag_value

union all

select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    null as student_number,
    null as grade_level,
    null as ada,
    null as ada_above_or_at_80,
    cast(null as date) as date_enrolled,

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
    r.sectionid,
    null as sections_dcid,
    null as section_number,
    '' as external_expression,
    null as section_or_period,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    null as is_ap_course,

    r.teacher_number,
    r.teacher_name,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,
    null as quarter_course_percent_grade_that_matters,
    null as quarter_course_grade_points_that_matters,
    null as quarter_citizenship,
    null as quarter_comment_value,

    r.teacher_assign_id,
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
    null as teacher_assign_count,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,
    r.cte_grouping,

    r.audit_flag_name,

    f.audit_category,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from
    class_category_assignment unpivot (
        audit_flag_value for audit_flag_name in (
            w_assign_max_score_not_10,
            f_assign_max_score_not_10,
            s_max_score_greater_100
        )
    ) as r
left join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.assignment_category_code = f.code
    and r.audit_flag_name = f.audit_flag_name
where audit_flag_value

union all

select
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.school_level,
    r.region_school_level,
    r.schoolid,
    r.school,

    null as student_number,
    null as grade_level,
    null as ada,
    null as ada_above_or_at_80,
    cast(null as date) as date_enrolled,

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
    r.sectionid,
    null as sections_dcid,
    null as section_number,
    '' as external_expression,
    null as section_or_period,
    r.credit_type,
    r.course_number,
    r.course_name,
    r.exclude_from_gpa,
    null as is_ap_course,

    r.teacher_number,
    r.teacher_name,

    null as category_quarter_percent_grade,
    null as category_quarter_average_all_courses,
    null as quarter_course_percent_grade_that_matters,
    null as quarter_course_grade_points_that_matters,
    null as quarter_citizenship,
    null as quarter_comment_value,

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
    null as teacher_assign_count,
    null as teacher_running_total_assign_by_cat,
    null as teacher_avg_score_for_assign_per_class_section_and_assign_id,

    null as raw_score,
    null as score_entered,
    null as assign_final_score_percent,
    null as is_exempt,
    null as is_late,
    null as is_missing,
    r.cte_grouping,

    r.audit_flag_name,

    f.audit_category,

    if(audit_flag_value, 1, 0) as audit_flag_value,

from
    class_category unpivot (
        audit_flag_value for audit_flag_name in (
            qt_teacher_s_total_greater_200,
            w_expected_assign_count_not_met,
            f_expected_assign_count_not_met,
            s_expected_assign_count_not_met
        )
    ) as r
left join
    {{ ref("stg_reporting__gradebook_flags") }} as f
    on r.region = f.region
    and r.school_level = f.school_level
    and r.assignment_category_code = f.code
    and r.audit_flag_name = f.audit_flag_name
where audit_flag_value
