with
    behaviors as (
        select
            _dbt_source_relation,
            dl_said,
            school_name,
            student_school_id,
            behavior_date,
            behavior_category,
            point_value,

            concat(staff_last_name, ', ', staff_first_name) as entry_staff,

            regexp_extract(_dbt_source_relation, r'(kipp\w+)_') as code_location,

            if(
                regexp_extract(_dbt_source_relation, r'(kipp\w+)_') = 'kippmiami',
                regexp_extract(behavior_category, r'([\w\s]+) \('),
                behavior
            ) as behavior,
        from {{ ref("stg_deanslist__behavior") }}
        where
            behavior_category in (
                'Earned Incentives',
                'Corrective Behaviors',
                'Values',
                'Be Kind (Love)',
                'Be Kind (Revolutionary Love)',
                'Effort (Perseverance)',
                'Effort (Pride)',
                'Accountability (Purpose, Courage)',
                'Accountability (Empowerment)',
                'Teamwork (Community)'
            )
            and behavior_date >= date({{ var("current_academic_year") - 1 }}, 7, 1)
    ),

    behavior_category_type as (
        select
            _dbt_source_relation,
            dl_said,
            school_name,
            student_school_id,
            behavior,
            behavior_date,
            behavior_category,
            point_value,
            entry_staff,

            case
                when behavior_category = 'Earned Incentives'
                then 'Incentives'
                when
                    code_location in ('kippnewark', 'kippcamden')
                    and behavior_category = 'Corrective Behaviors'
                then 'Corrective'
                when
                    code_location in ('kippnewark', 'kippcamden')
                    and behavior_category = 'Values'
                then 'BEAT'
                when
                    code_location = 'kippmiami'
                    and behavior_category in ('Written Reminders', 'Big Reminders')
                then 'Corrective'
                when
                    code_location = 'kippmiami'
                    and behavior_category
                    in ('Be Kind', 'Effort', 'Accountability', 'Teamwork')
                then 'BEAT'
            end as category_type,
        from behaviors
    ),

    behavior_week as (
        select
            b._dbt_source_relation,
            b.dl_said,
            b.student_school_id,
            b.behavior,
            b.behavior_category,
            b.point_value,
            b.category_type,
            b.entry_staff,

            w.academic_year,
            w.quarter as term,
            w.week_start_monday,
            w.week_end_sunday,
            w.date_count as days_in_session,
        from behavior_category_type as b
        inner join
            {{ ref("stg_people__location_crosswalk") }} as lc on b.school_name = lc.name
        inner join
            {{ ref("int_powerschool__calendar_week") }} as w
            on b.behavior_date between w.week_start_monday and w.week_end_sunday
            and {{ union_dataset_join_clause(left_alias="w", right_alias="b") }}
            and lc.powerschool_school_id = w.schoolid
        where b.category_type is not null
    ),

    behavior_aggregation as (
        select
            _dbt_source_relation,
            student_school_id,
            behavior,
            behavior_category,
            category_type,
            academic_year,
            term,
            week_start_monday,
            week_end_sunday,
            days_in_session,
            entry_staff,

            sum(point_value) as total_points,
            count(distinct dl_said) as behavior_count,
        from behavior_week
        group by all
    )

select
    co.student_number,
    co.lastfirst as student_name,
    co.enroll_status,
    co.cohort,
    co.academic_year,
    co.region,
    co.school_level,
    co.school_abbreviation as school,
    co.grade_level,
    co.gender,
    co.ethnicity,
    co.lunch_status,
    co.is_retained_year,
    co.rn_year,

    cw.quarter as term,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.date_count as days_in_session,

    b.category_type,
    b.behavior,
    b.entry_staff,
    b.total_points,
    b.behavior_count,

    hr.sections_section_number as homeroom_section,
    hr.teacher_lastfirst as homeroom_teacher_name,

    if(co.lep_status, 'ML', 'Not ML') as ml_status,
    if(co.is_504, 'Has 504', 'No 504') as status_504,
    if(co.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,
    if(
        co.is_self_contained, 'Self-contained', 'Not self-contained'
    ) as self_contained_status,

    count(distinct co.student_number) over (
        partition by co.schoolid, cw.week_start_monday
    ) as school_enrollment_by_week,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("int_powerschool__calendar_week") }} as cw
    on co.schoolid = cw.schoolid
    and co.academic_year = cw.academic_year
    and cw.week_start_monday between co.entrydate and co.exitdate
    and {{ union_dataset_join_clause(left_alias="co", right_alias="cw") }}
left join
    behavior_aggregation as b
    on co.student_number = b.student_school_id
    and co.academic_year = b.academic_year
    and cw.week_start_monday = b.week_start_monday
    and {{ union_dataset_join_clause(left_alias="co", right_alias="b") }}
left join
    {{ ref("base_powerschool__course_enrollments") }} as hr
    on co.studentid = hr.cc_studentid
    and co.yearid = hr.cc_yearid
    and co.schoolid = hr.cc_schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="hr") }}
    and hr.cc_course_number = 'HR'
    and hr.rn_course_number_year = 1
    and not hr.is_dropped_section
where
    co.academic_year >= {{ var("current_academic_year") - 1 }} and co.grade_level != 99
