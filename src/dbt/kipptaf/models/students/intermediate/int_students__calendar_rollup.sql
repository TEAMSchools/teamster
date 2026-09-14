with
    focus_schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    focus_conformed as (
        -- trunk-ignore(sqlfluff/ST06): column order matches the PowerSchool arm's
        select
            cr.days_total,
            cr.days_remaining,

            cr._dbt_source_relation,
            cr._dbt_source_project,

            fs.schoolid,

            cr.academic_year - 1990 as yearid,
            cr.min_school_date as min_calendardate,
            cr.max_school_date as max_calendardate,

            cast(null as string) as track,
        from {{ ref("int_focus__calendar_rollup") }} as cr
        inner join focus_schools as fs on cr.schoolid = fs.focus_school_id
        -- One row. Floors on the cutover year, not on Focus row presence
        -- (#5193).
        cross join {{ ref("int_students__sis_cutover") }} as c
        where cr.academic_year >= c.focus_start_academic_year
    )

select
    _dbt_source_relation,
    schoolid,
    yearid,
    track,
    min_calendardate,
    max_calendardate,
    days_total,
    days_remaining,
    _dbt_source_project,
from {{ ref("int_powerschool__calendar_rollup") }}

union all

select
    _dbt_source_relation,
    schoolid,
    yearid,
    track,
    min_calendardate,
    max_calendardate,
    days_total,
    days_remaining,
    _dbt_source_project,
from focus_conformed
