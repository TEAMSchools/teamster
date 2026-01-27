with
    daily_spine as (
        -- need only one row per expected sre academic year
        select distinct academic_year, calendar_day,

        from {{ ref("int_finalsite__status_report") }}
        cross join
            unnest(
                generate_date_array(
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc(sre_year_start, week(monday)),
                    -- trunk-ignore(sqlfluff/LT01)
                    date_trunc(sre_year_end, week(monday)),
                    interval 1 day
                )
            ) as calendar_day
        where rn = 1
    )

select
    f._dbt_source_relation,
    f.academic_year,
    f.enrollment_academic_year_display,
    f.org,
    f.region,
    f.schoolid,
    f.school,
    f.grade_level,
    f.sre_year_start,
    f.sre_year_end,
    f.week_start_monday,
    f.week_end_sunday,
    f.enrollment_type,
    f.overall_status,
    f.funnel_status,
    f.status_category,
    f.offered_status,
    f.offered_status_detailed,
    f.detailed_status,
    f.detailed_status_ranking,
    f.detailed_status_branched_ranking,
    f.powerschool_enroll_status,
    f.valid_detailed_status,
    f.finalsite_student_id,
    f.student_finalsite_student_id,
    f.student_enrollment_year,
    f.student_region,
    f.student_schoolid,
    f.student_school,
    f.student_number,
    f.student_last_name,
    f.student_first_name,
    f.student_grade_level,
    f.student_grade_level_string,
    f.student_detailed_status,
    f.status_start_date,
    f.status_end_date,
    f.days_in_status,
    f.student_enrollment_type,

    d.calendar_day,

    first_value(f.student_detailed_status) over (
        partition by f.academic_year, f.finalsite_student_id
        order by f.status_start_date desc
    ) as latest_status,

from {{ ref("int_students__finalsite_student_roster") }} as f
inner join
    daily_spine as d on d.calendar_day between f.week_start_monday and f.week_end_sunday
