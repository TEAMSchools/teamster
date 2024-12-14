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
