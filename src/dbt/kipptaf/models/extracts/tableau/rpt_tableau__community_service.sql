select
    co.student_number,
    co.academic_year,
    co.lastfirst,
    co.gender,
    co.ethnicity,
    co.spedlep as iep_status,
    co.lep_status,
    co.is_504 as c_504_status,
    co.grade_level,
    co.cohort,
    co.advisor_lastfirst as advisor_name,
    co.contact_1_email_current as guardianemail,
    co.student_email_google as student_email,
    co.school_abbreviation as school_name,

    b.behavior_date,
    b.behavior,
    b.notes,

    cast(left(b.behavior, length(b.behavior) - 5) as int64) as cs_hours,
    concat(b.staff_last_name, ', ', b.staff_first_name) as staff_name,
from {{ ref("base_powerschool__student_enrollments") }} as co
left join
    {{ ref("stg_deanslist__behavior") }} as b
    on co.student_number = b.student_school_id
    and {{ union_dataset_join_clause(left_alias="co", right_alias="b") }}
    and b.behavior_category = 'Community Service'
    and b.behavior_date between co.entrydate and co.exitdate
where co.grade_level >= 9 and co.enroll_status = 0 and co.rn_year = 1
