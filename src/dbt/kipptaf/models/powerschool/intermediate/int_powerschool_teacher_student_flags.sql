with
    expected_flags as (
        select
            t._dbt_source_relation,
            t.school_level,
            t.quarter,
            t.week_number_quarter,
            t.schoolid,

            t.sectionid,

            t.assignment_category_code,
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

            t.teacher_avg_score_for_assign_per_class_section_and_assign_id,

            f.audit_category,
            f.audit_flag_name,
            f.cte_grouping,

        from {{ ref("int_powerschool__teacher_assignment_audit_base") }} as t
        left join
            {{ ref("stg_reporting__gradebook_flags") }} as f
            on t.region = f.region
            and t.school_level = f.school_level
            and t.assignment_category_code = f.code
            and f.cte_grouping = 'assignment_student'
    )

select
    t._dbt_source_relation,
    t.school_level,
    t.quarter,
    t.week_number_quarter,
    t.schoolid,

    t.sectionid,

    t.assignment_category_code,
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

    t.teacher_avg_score_for_assign_per_class_section_and_assign_id,

    f.audit_category,
    f.audit_flag_name,
    f.cte_grouping,

    a.student_number,
    a.raw_score,
    a.score_entered,
    a.assign_final_score_percent,
    a.is_exempt,
    a.is_late,
    a.is_missing,

    a.audit_flag_name,
    a.audit_flag_value,

from expected_flags as t
left join
    {{ ref("int_tableau__gradebook_audit_flags") }} as a
    on t.quarter = a.quarter
    and t.week_number_quarter = a.week_number
    and t.schoolid = a.schoolid
    and t.sectionid = a.sectionid
    and t.assignment_category_code = a.assignment_category_code
    and t.teacher_assign_id = a.teacher_assign_id
    and t.cte_grouping = a.cte_grouping
