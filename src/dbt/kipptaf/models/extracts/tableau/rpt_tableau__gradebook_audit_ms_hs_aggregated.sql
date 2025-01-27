{{- config(materialized="table") -}}

with
    teacher_aggs as (
        select
            _dbt_source_relation,
            academic_year,
            region,
            school,

            quarter,
            is_current_quarter,
            audit_qt_week_number,
            quarter_start_date,
            quarter_end_date,
            audit_start_date,
            audit_end_date,

            teacher_name,

            sum(audit_flag_value) as teacher_error_count,

            count(*) as teacher_possible_errors,

            round(
                1 - (sum(audit_flag_value) / count(*)), 4
            ) as teacher_percent_complete_for_audit_week,

            if(
                round(1 - (sum(audit_flag_value) / count(*)), 4) = 1, 1, 0
            ) teacher_gradebook_done_for_audit_week,

        from {{ ref("rpt_tableau__gradebook_audit_ms_hs") }}
        where
            audit_flag_name
            not in ('qt_student_is_ada_80_plus_gpa_less_2', 'w_grade_inflation')
        group by all
    )

select
    _dbt_source_relation,
    academic_year,
    region,
    school,
    quarter,
    is_current_quarter,
    audit_qt_week_number,
    quarter_start_date,
    quarter_end_date,
    audit_start_date,
    audit_end_date,
    teacher_name,

    teacher_error_count,
    teacher_possible_errors,
    teacher_percent_complete_for_audit_week,

    sum(teacher_gradebook_done_for_audit_week) over (
        partition by school, quarter, audit_qt_week_number
    ) as school_teachers_done_for_audit_week,

    count(teacher_name) over (
        partition by school, quarter, audit_qt_week_number
    ) as school_teachers_total_for_audit_week,

    round(
        safe_divide(
            sum(teacher_gradebook_done_for_audit_week) over (
                partition by school, quarter, audit_qt_week_number
            ),
            count(teacher_name) over (
                partition by school, quarter, audit_qt_week_number
            )
        ),
        4
    ) as school_percent_teachers_done_for_audit_week,

from teacher_aggs
