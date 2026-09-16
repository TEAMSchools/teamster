with
    focus_schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    powerschool_dated as (
        select
            cd._dbt_source_relation,
            cd._dbt_source_project,
            cd.schoolid,
            cd.insession,
            cd.membershipvalue,
            cd.week_start_date,
            cd.week_end_date,
            cd.date_value,
            cd.date_value as school_date,

            cd.yearid,

            cd.insession = 1 as is_in_session,
            cd.membershipvalue > 0 as is_in_membership,
        from {{ ref("int_powerschool__calendar_day") }} as cd
        -- PowerSchool carries a handful of pre-2000 sentinel junk rows. The old
        -- source (kipptaf's stg_powerschool__calendar_day) nulled their
        -- date_value and this model dropped the nulls; the package's
        -- int_powerschool__calendar_day passes them through, so drop them by
        -- date here instead -- they were never real calendar days.
        where cd.date_value >= date '2000-01-01'
    ),

    powerschool_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            schoolid,
            insession,
            membershipvalue,
            week_start_date,
            week_end_date,
            date_value,
            school_date,
            yearid,
            is_in_session,
            is_in_membership,

            yearid + 1990 as academic_year,
        from powerschool_dated
    ),

    focus_conformed as (
        select
            cd._dbt_source_relation,
            cd._dbt_source_project,
            cd.week_start_date,
            cd.week_end_date,

            fs.schoolid,

            cd.school_date as date_value,
            cd.school_date,
            cd.academic_year,

            1 as insession,
            cast(1 as float64) as membershipvalue,
            true as is_in_session,
            true as is_in_membership,

            cd.academic_year - 1990 as yearid,
        from {{ ref("int_focus__calendar_day") }} as cd
        inner join focus_schools as fs on cd.schoolid = fs.focus_school_id
        -- One row. Floors on the cutover year, not on Focus row presence
        -- (#5193).
        cross join {{ ref("int_students__sis_cutover") }} as c
        where cd.academic_year >= c.focus_start_academic_year
    )

-- `union all` matches columns by POSITION, so both branches list the same
-- 13 columns in the same order. Enumerating also fixes the view's column list:
-- BigQuery sets it at create time and Dagster rebuilds a view only when its
-- raw SQL changes, so a `select *` branch never picks up a column added
-- upstream.
select
    _dbt_source_relation,
    _dbt_source_project,
    schoolid,
    insession,
    membershipvalue,
    week_start_date,
    week_end_date,
    date_value,
    school_date,
    yearid,
    is_in_session,
    is_in_membership,
    academic_year,
from powerschool_conformed

union all

select
    _dbt_source_relation,
    _dbt_source_project,
    schoolid,
    insession,
    membershipvalue,
    week_start_date,
    week_end_date,
    date_value,
    school_date,
    yearid,
    is_in_session,
    is_in_membership,
    academic_year,
from focus_conformed
