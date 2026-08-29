with
    behaviors_typed as (
        select
            b._dbt_source_relation,
            b._dbt_source_project,
            b.dl_said,
            b.school_name,
            b.student_school_id,
            b.behavior_date,
            b.behavior_category,
            b.point_value,
            b.staff_full_name as entry_staff,

            /* Miami and New Jersey category names are disjoint, so these
               branches need no region guard. Dropping the guard is what closes
               the old NULL hole: a category that passed the allowlist but
               matched no branch used to survive with a null category_type,
               invisible to every workbook filter but still fanning out the
               spine columns. The `category_type is not null` filter below now
               makes the allowlist and the CASE the same list. */
            case
                when b.behavior_category in ('Written Reminders', 'Big Reminders')
                then 'Corrective'
                when
                    b.behavior_category in (
                        'Accountability (Empowerment)',
                        'Accountability (Purpose, Courage)',
                        'Be Kind (Love)',
                        'Be Kind (Revolutionary Love)',
                        'Effort (Perseverance)',
                        'Effort (Pride)',
                        'Teamwork (Community)'
                    )
                then 'BEAT'
                when
                    b.behavior_category
                    in ('Corrective Behaviors', 'Tier 1 - Corrective Behaviors')
                then 'Corrective'
                when b.behavior_category = 'Tier 1 - Habits of Excellence Corrections'
                then 'Habits of Excellence'
                when
                    b.behavior_category
                    in ('Values', 'Values (5)', 'Values (10 Point Bonus)')
                then 'BEAT'
            end as category_type,

            case
                when b._dbt_source_relation like '%kippmiami%'
                then regexp_extract(b.behavior_category, r'([\w\s]+) \(')
                when b.behavior like '%(%)'
                then regexp_extract(b.behavior, r'([\w\s]+) \(')
                else b.behavior
            end as behavior_extracted,
        from {{ ref("stg_deanslist__behavior") }} as b
        where b.behavior_date >= '{{ var("current_academic_year") - 1 }}-07-01'
    ),

    behaviors as (
        select
            bt._dbt_source_relation,
            bt._dbt_source_project,
            bt.dl_said,
            bt.school_name,
            bt.student_school_id,
            bt.behavior_date,
            bt.behavior_category,
            bt.point_value,
            bt.entry_staff,
            bt.category_type,

            w.academic_year,
            w.quarter as term,
            w.week_start_monday,
            w.week_end_sunday,
            w.date_count as days_in_session,

            /* Normalize the EXTRACTED value, not the raw one. An equality test
               written before the parenthetical-stripping regex would miss a
               'TEAMwork (Community)'-shaped name. `Values` logs TEAMwork while
               `Values (5)` and `Values (10 Point Bonus)` log Teamwork, so
               without this the same value splits into two members inside a
               single year -- and the workbook's colour map and manual sort
               only know 'Teamwork'. */
            case
                when bt.behavior_extracted = 'TEAMwork'
                then 'Teamwork'
                else bt.behavior_extracted
            end as behavior,
        from behaviors_typed as bt
        inner join
            {{ ref("int_people__location_crosswalk") }} as lc
            on bt.school_name = lc.location_name
        inner join
            {{ ref("int_students__calendar_week") }} as w
            on bt.behavior_date between w.week_start_monday and w.week_end_sunday
            and w._dbt_source_project = bt._dbt_source_project
            and lc.location_powerschool_school_id = w.schoolid
        where bt.category_type is not null
    ),

    behavior_aggregation as (
        select
            _dbt_source_relation,
            _dbt_source_project,
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
            _dbt_source_project,
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
    ),

    okrts_behavior as (
        select
            co._dbt_source_project,
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
            co.iep_status,
            co.ml_status,
            co.status_504,
            co.self_contained_status,
            co.homeless_status,
            co.homeless_primary_nighttime_residence,
            co.quarter as term,
            co.week_start_monday,
            co.week_end_sunday,
            co.date_count as days_in_session,

            b.behavior_category,
            b.category_type,
            b.behavior,
            b.entry_staff,
            b.total_points,
            b.behavior_count,

            if(bi.behavior is not null, 1, 0) as is_earned_progress_to_quarterly,

            if(bq.behavior is not null, 1, 0) as is_earned_quarterly_incentive,

            extract(month from co.week_start_monday) as behavior_month,

            count(distinct co.student_number) over (
                partition by co.schoolid, co.week_start_monday
            ) as school_enrollment_by_week,

            count(
                distinct if(co.iep_status = 'Has IEP', co.student_number, null)
            ) over (partition by co.schoolid, co.week_start_monday)
            as school_iep_enrollment_by_week,
        from {{ ref("int_extracts__student_enrollments_weeks") }} as co
        left join
            behavior_aggregation as b
            on co.student_number = b.student_school_id
            and co.academic_year = b.academic_year
            and co.week_start_monday = b.week_start_monday
            and co._dbt_source_project = b._dbt_source_project
        left join
            {{ ref("int_deanslist__behavior_incentive_by_term") }} as bi
            on co.student_number = bi.student_school_id
            and co.deanslist_school_id = bi.school_id
            and co.academic_year = bi.academic_year
            and bi.end_date between co.week_start_monday and co.week_end_sunday
            and bi.incentive_type = 'Weeks (Progress to Quarterly Incentive)'
        left join
            {{ ref("int_deanslist__behavior_incentive_by_term") }} as bq
            on co.student_number = bq.student_school_id
            and co.deanslist_school_id = bq.school_id
            and co.academic_year = bq.academic_year
            and co.quarter = bq.term_name
            and bq.incentive_type = 'Quarters'
        where
            co.is_enrolled_week
            and co.academic_year >= {{ var("current_academic_year") - 1 }}
    )

select * except (_dbt_source_project),
from okrts_behavior
where {{ exclude_deanslist_stopped("_dbt_source_project", "academic_year") }}
