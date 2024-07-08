with
    behavior_categories as (
        select region, 'BEAT' as category_type, 'Values' as behavior_category,
        from unnest(['Camden', 'Newark']) as region
        union all
        select 'Miami' as region, 'BEAT' as category_type, behavior_category,
        from
            unnest(
                [
                    'Be Kind (Love)',
                    'Be Kind (Revolutionary Love)',
                    'Effort (Perseverance)',
                    'Effort (Pride)',
                    'Accountability (Purpose, Courage)',
                    'Accountability (Empowerment)',
                    'Teamwork (Community)'
                ]
            ) as behavior_category
        union all
        select 'Miami' as region, 'Corrective' as category_type, behavior_category,
        from unnest(['Written Reminders', 'Big Reminders']) as behavior_category
    ),

    roster as (
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
            co.lunch_status,
            co.is_retained_year,

            w.week_start_monday,
            w.week_end_sunday,
            w.date_count as days_in_session,
            w.quarter as term,

            bc.category_type,

            b.dl_said,
            b.point_value,

            concat(b.staff_last_name, ', ', b.staff_first_name) as entry_staff,
            case
                when co.region = 'Miami'
                then regexp_extract(b.behavior_category, r'^(.*?) \(')
                else b.behavior
            end as behavior,
            
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
        left join
            {{ ref("stg_deanslist__behavior") }} as b
            on co.student_number = b.student_school_id
            and b.behavior_date between w.week_start_monday and w.week_end_sunday
        inner join
            behavior_categories as bc
            on co.region = bc.region
            and b.behavior_category = bc.behavior_category
        where
            co.academic_year >= {{ var("current_academic_year") }} - 1
            and co.rn_year = 1
            and co.grade_level != 99
    )

select
    r.student_number,
    r.student_name,
    r.academic_year,
    r.schoolid,
    r.school,
    r.region,
    r.grade_level,
    r.enroll_status,
    r.cohort,
    r.school_level,
    r.gender,
    r.ethnicity,
    r.week_start_monday,
    r.week_end_sunday,
    r.days_in_session,
    r.term,
    r.category_type,
    r.behavior,
    r.entry_staff,
    r.ml_status,
    r.status_504,
    r.self_contained_status,
    r.iep_status,
    count(distinct r.dl_said) as behavior_count,
    sum(r.point_value) as total_points,
from roster as r
group by
    r.student_number,
    r.student_name,
    r.academic_year,
    r.schoolid,
    r.school,
    r.region,
    r.grade_level,
    r.enroll_status,
    r.cohort,
    r.school_level,
    r.gender,
    r.ethnicity,
    r.week_start_monday,
    r.week_end_sunday,
    r.days_in_session,
    r.term,
    r.category_type,
    r.behavior,
    r.entry_staff,
    r.ml_status,
    r.status_504,
    r.self_contained_status,
    r.iep_status
