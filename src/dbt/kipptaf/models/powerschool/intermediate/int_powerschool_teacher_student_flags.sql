select
    t._dbt_source_relation,
    t.quarter,
    t.week_number_quarter,
    t.schoolid,

    t.sectionid,
    t.assignment_category_code,
    t.teacher_assign_id,

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

    /*
    a.student_number,
    a.raw_score,
    a.score_entered,
    a.assign_final_score_percent,
    a.is_exempt,
    a.is_late,
    a.is_missing,

    a.cte_grouping,
    a.audit_flag_name,
    a.audit_flag_value,

left join
    {{ ref("int_tableau__gradebook_audit_flags") }} as a
    on t.quarter = a.quarter
    and t.week_number_quarter = a.week_number
    and t.schoolid = a.schoolid
    and t.sectionid = a.sectionid
    and t.assignment_category_code = a.assignment_category_code
    and t.teacher_assign_id = a.teacher_assign_id
    and a.cte_grouping = 'assignment_student'
    */
    