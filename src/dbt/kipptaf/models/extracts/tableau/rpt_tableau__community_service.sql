select
    co.student_number,
    co.academic_year,
    co.student_name,
    co.gender,
    co.ethnicity,
    co.iep_status,
    co.lep_status,
    co.is_504 as c_504_status,
    co.grade_level,
    co.cohort,
    co.advisory as advisor_name,
    co.guardian_email,
    co.student_email,
    co.school as school_name,

    b.behavior_date,
    b.behavior,
    b.notes,

    coalesce(safe_cast(left(b.behavior, length(b.behavior) - 5) as int), 0) as cs_hours,
    concat(b.staff_last_name, ', ', b.staff_first_name) as staff_name,

    coalesce(safe_cast(c.`9th_hours` as numeric), 0) as grade_9_hours,
    coalesce(safe_cast(c.`10th_hours` as numeric), 0) as grade_10_hours,
    coalesce(safe_cast(c.`11th_hours` as numeric), 0) as grade_11_hours,
    coalesce(safe_cast(c.`12th_hours` as numeric), 0) as grade_12_hours,
from {{ ref("int_tableau__student_enrollments") }} as co
left join
    {{ ref("stg_deanslist__behavior") }} as b
    on co.student_number = b.student_school_id
    and {{ union_dataset_join_clause(left_alias="co", right_alias="b") }}
    and b.behavior_category in ('Community Service', 'Community Service Hours')
    and b.behavior_date between co.entrydate and co.exitdate
left join
    {{ ref("int_deanslist__students__custom_fields__pivot") }} as c
    on co.student_number = safe_cast(c.student_school_id as int64)
where
    co.grade_level >= 9
    and co.enroll_status = 0
    and co.academic_year = {{ var("current_academic_year") }}
