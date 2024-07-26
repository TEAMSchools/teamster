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

        union all

        select
            region,
            'Incentives' as category_type,
            'Earned Incentives' as behavior_category,
        from unnest(['Camden', 'Newark', 'Miami']) as region
    ),

    roster as (
        select
            co._dbt_source_relation,
            co.studentid,
            co.yearid,
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
            if(
                co.region = 'Miami',
                regexp_extract(b.behavior_category, r'^(.*?) \('),
                b.behavior
            ) as behavior,

            count(distinct co.student_number) over (
                partition by w.week_start_monday, co.school_abbreviation
            ) as school_enrollment_by_week,

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
            and {{ union_dataset_join_clause(left_alias="co", right_alias="w") }}
        left join
            {{ ref("stg_deanslist__behavior") }} as b
            on co.student_number = b.student_school_id
            and b.behavior_date between w.week_start_monday and w.week_end_sunday
            and {{ union_dataset_join_clause(left_alias="co", right_alias="b") }}
        inner join
            behavior_categories as bc
            on co.region = bc.region
            and b.behavior_category = bc.behavior_category
        where
            co.academic_year >= {{ var("current_academic_year") }} - 1
            and co.rn_year = 1
            and co.grade_level != 99
    ),

    behavior_aggregation as (
        select
            student_number,
            academic_year,
            week_start_monday,
            category_type,
            behavior,
            entry_staff,

            count(distinct dl_said) as behavior_count,
            sum(point_value) as total_points,
        from roster
        group by
            student_number,
            academic_year,
            week_start_monday,
            category_type,
            behavior,
            entry_staff
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
    r.school_enrollment_by_week,
    r.ml_status,
    r.status_504,
    r.self_contained_status,
    r.iep_status,

    hr.sections_section_number as homeroom_section,
    hr.teacher_lastfirst as homeroom_teacher_name,

    b.category_type,
    b.behavior,
    b.entry_staff,
    b.behavior_count,
    b.total_points,
from roster as r
left join
    {{ ref("base_powerschool__course_enrollments") }} as hr
    on r.studentid = hr.cc_studentid
    and r.yearid = hr.cc_yearid
    and r.schoolid = hr.cc_schoolid
    and {{ union_dataset_join_clause(left_alias="r", right_alias="hr") }}
    and hr.cc_course_number = 'HR'
    and not hr.is_dropped_section
    and hr.rn_course_number_year = 1
left join
    behavior_aggregation as b
    on r.student_number = b.student_number
    and r.academic_year = b.academic_year
    and r.week_start_monday = b.week_start_monday
