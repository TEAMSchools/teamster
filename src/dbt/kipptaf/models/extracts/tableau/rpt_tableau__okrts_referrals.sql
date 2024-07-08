select
    co.student_number,
    co.lastfirst as student_name,
    co.academic_year,
    co.schoolid,
    co.school_abbreviation as school,
    co.region,
    co.grade_level,
    co.enroll_status,
    co.cohort,
    co.school_level,
    co.gender,
    co.ethnicity,
    w.week_start_monday,
    w.week_end_sunday,
    w.date_count as days_in_session,
    w.quarter as term,
    -- bc.category_type,
    -- b.dl_said,
    -- b.point_value,
    -- concat(b.staff_last_name, ', ', b.staff_first_name) as entry_staff,
    -- case
    -- when co.region = 'Miami'
    -- then regexp_extract(b.behavior_category, r'^(.*?) \(')
    -- else b.behavior
    -- end as behavior,
    if(co.lep_status, 'ML', 'Not ML') as ml_status,
    if(co.is_504, 'Has 504', 'No 504') as status_504,
    if(
        co.is_self_contained, 'Self-contained', 'Not self-contained'
    ) as self_contained_status,
    if(co.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("int_powerschool__calendar_week") }} as w
    on co.academic_year = w.academic_year
    and co.schoolid = w.schoolid
    and w.week_end_sunday between co.entrydate and co.exitdate
-- left join
-- {{ ref("stg_deanslist__behavior") }} as b
-- on co.student_number = b.student_school_id
-- and b.behavior_date between w.week_start_monday and w.week_end_sunday
-- inner join
-- behavior_categories as bc
-- on co.region = bc.region
-- and b.behavior_category = bc.behavior_category
where
    co.academic_year >= {{ var("current_academic_year") }} - 1
    and co.rn_year = 1
    and co.grade_level != 99
