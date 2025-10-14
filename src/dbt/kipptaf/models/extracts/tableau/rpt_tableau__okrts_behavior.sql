with
    behaviors as (
        select
            b._dbt_source_relation,
            b.dl_said,
            b.school_name,
            b.student_school_id,
            b.behavior_date,
            b.behavior_category,
            b.point_value,
            b.staff_full_name as entry_staff,

            w.academic_year,
            w.quarter as term,
            w.week_start_monday,
            w.week_end_sunday,
            w.date_count as days_in_session,

            case
                when
                    b._dbt_source_relation like '%kippmiami%'
                    and b.behavior_category != 'Earned Incentives'
                then regexp_extract(b.behavior_category, r'([\w\s]+) \(')
                when b.behavior like '%(%)'
                then regexp_extract(b.behavior, r'([\w\s]+) \(')
                else b.behavior
            end as behavior,

            case
                -- when b.behavior_category = 'Earned Incentives'
                -- then 'Incentives'
                /* Miami */
                when
                    b._dbt_source_relation like '%kippmiami%'
                    and b.behavior_category in ('Written Reminders', 'Big Reminders')
                then 'Corrective'
                when
                    b._dbt_source_relation like '%kippmiami%'
                    and b.behavior_category in (
                        'Be Kind (Love)',
                        'Be Kind (Revolutionary Love)',
                        'Effort (Perseverance)',
                        'Effort (Pride)',
                        'Accountability (Purpose, Courage)',
                        'Accountability (Empowerment)',
                        'Teamwork (Community)'
                    )
                then 'BEAT'
                /* all other regions */
                when
                    b._dbt_source_relation not like '%kippmiami%'
                    and b.behavior_category = 'Corrective Behaviors'
                then 'Corrective'
                when
                    b._dbt_source_relation not like '%kippmiami%'
                    and b.behavior_category = 'Values'
                then 'BEAT'
            end as category_type,
        from {{ ref("stg_deanslist__behavior") }} as b
        inner join
            {{ ref("stg_people__location_crosswalk") }} as lc on b.school_name = lc.name
        inner join
            {{ ref("int_powerschool__calendar_week") }} as w
            on b.behavior_date between w.week_start_monday and w.week_end_sunday
            and {{ union_dataset_join_clause(left_alias="w", right_alias="b") }}
            and lc.powerschool_school_id = w.schoolid
        where
            b.behavior_category in (
                'Accountability (Empowerment)',
                'Accountability (Purpose, Courage)',
                'Be Kind (Love)',
                'Be Kind (Revolutionary Love)',
                'Big Reminders',
                'Corrective Behaviors',
                -- 'Earned Incentives',
                'Effort (Perseverance)',
                'Effort (Pride)',
                'Teamwork (Community)',
                'Values',
                'Written Reminders'
            )
            and b.behavior_date >= '{{ var("current_academic_year") - 1 }}-07-01'
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
        from behaviors
        group by
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
            entry_staff
    )

select
    co.student_number,
    co.state_studentnumber,
    co.student_name,
    co.enroll_status,
    co.cohort,
    co.academic_year,
    co.region,
    co.school_level,
    co.school,
    co.grade_level,
    co.gender,
    co.ethnicity,
    co.lunch_status,
    co.is_retained_year,
    co.rn_year,
    co.team as homeroom_section,
    co.advisor_lastfirst as homeroom_teacher_name,

    cw.quarter as term,
    cw.week_start_monday,
    cw.week_end_sunday,
    cw.date_count as days_in_session,

    b.category_type,
    b.behavior,
    b.entry_staff,
    b.total_points,
    b.behavior_count,

    if(bi.behavior is not null, 1, 0) as is_earned_progress_to_quarterly,

    extract(month from cw.week_start_monday) as behavior_month,

    if(co.lep_status, 'ML', 'Not ML') as ml_status,
    if(co.is_504, 'Has 504', 'No 504') as status_504,
    if(co.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,
    if(
        co.is_self_contained, 'Self-contained', 'Not self-contained'
    ) as self_contained_status,

    count(distinct co.student_number) over (
        partition by co.schoolid, cw.week_start_monday
    ) as school_enrollment_by_week,
from {{ ref("int_extracts__student_enrollments") }} as co
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
    {{ ref("int_deanslist__behavior_incentive_by_term") }} as bi
    on co.student_number = bi.student_school_id
    and co.deanslist_school_id = bi.school_id
    and co.academic_year = bi.academic_year
    and bi.end_date between cw.week_start_monday and cw.week_end_sunday
    and bi.incentive_type = 'Weeks (Progress to Quarterly Incentive)'
where co.academic_year >= {{ var("current_academic_year") - 1 }}
