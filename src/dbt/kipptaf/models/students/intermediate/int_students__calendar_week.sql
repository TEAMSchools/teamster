with
    focus_schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    focus_conformed as (
        select
            cw.* except (schoolid, academic_year),

            fs.schoolid,

            cw.academic_year,
            cw.academic_year - 1990 as yearid,

            {{ extract_region("cw") }} as region,
        from {{ ref("int_focus__calendar_week") }} as cw
        inner join focus_schools as fs on cw.schoolid = fs.focus_school_id
        -- Floors on the cutover year, not on Focus row presence (#5193).
        where cw.academic_year >= 2026
    )

select
    _dbt_source_relation,
    schoolid,
    week_start_date,
    week_end_date,
    school_level,
    yearid,
    academic_year,
    week_start_monday,
    week_end_sunday,
    school_week_start_date,
    school_week_end_date,
    date_count,
    semester,
    quarter,
    first_day_school_year,
    last_week_start_school_year,
    last_day_school_year,
    school_week_start_date_lead,
    week_number_academic_year,
    week_number_quarter,
    is_current_week_mon_sun,
    region,
    _dbt_source_project,
from {{ ref("int_powerschool__calendar_week") }}

union all

select
    _dbt_source_relation,
    schoolid,
    week_start_date,
    week_end_date,
    school_level,
    yearid,
    academic_year,
    week_start_monday,
    week_end_sunday,
    school_week_start_date,
    school_week_end_date,
    date_count,
    semester,
    quarter,
    first_day_school_year,
    last_week_start_school_year,
    last_day_school_year,
    school_week_start_date_lead,
    week_number_academic_year,
    week_number_quarter,
    is_current_week_mon_sun,
    region,
    _dbt_source_project,
from focus_conformed
