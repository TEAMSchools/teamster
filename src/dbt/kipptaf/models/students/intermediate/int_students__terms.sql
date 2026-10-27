with
    focus_schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    focus_marking_periods as (
        select
            mp._dbt_source_relation,
            mp._dbt_source_project,
            mp.type,
            mp.title,
            mp.short_name,
            mp.start_date,
            mp.end_date,
            mp.quarter_semester,
            mp.is_within_dates,

            mp.syear as academic_year,

            fs.schoolid,
        from {{ ref("stg_focus__marking_periods") }} as mp
        inner join focus_schools as fs on mp.school_id = fs.focus_school_id
        -- Progress periods have no PowerSchool `terms` equivalent. The 2026
        -- floor is the SIS cutover year: before it the frozen PowerSchool
        -- archive owns Miami's terms, while Focus carries a full
        -- year/semester/quarter set back to 1980 for a handful of schools,
        -- which would fabricate history here. Both filters stay in this model
        -- rather than in staging, because Focus report card grades point at
        -- pre-cutover marking periods that flooring the staging model would
        -- orphan.
        where mp.type in ('year', 'semester', 'quarter') and mp.syear >= 2026
    ),

    focus_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            schoolid,
            academic_year,

            title as `name`,
            short_name as abbreviation,
            start_date as firstday,
            end_date as lastday,

            if(`type` = 'year', 1, 0) as isyearrec,

            academic_year - 1990 as yearid,
            academic_year + 1 as fiscal_year,

            if(`type` = 'quarter', short_name, null) as term,
            if(`type` = 'quarter', start_date, null) as term_start_date,
            if(`type` = 'quarter', end_date, null) as term_end_date,
            if(`type` = 'quarter', quarter_semester, null) as semester,
            if(`type` = 'quarter', is_within_dates, null) as is_current_term,
        from focus_marking_periods
    ),

    term_calendar as (
        select
            _dbt_source_project,
            academic_year,
            schoolid,
            term,
            first_day_school_year,
            last_day_school_year,

            sum(date_count) as days_in_term,
        from {{ ref("int_students__calendar_week") }}
        group by
            _dbt_source_project,
            academic_year,
            schoolid,
            term,
            first_day_school_year,
            last_day_school_year
    ),

    terms_union as (
        select
            _dbt_source_relation,
            dcid,
            `name`,
            firstday,
            lastday,
            abbreviation,
            importmap,
            terminfo_guid,
            psguid,
            ip_address,
            whomodifiedtype,
            transaction_date,
            id,
            noofdays,
            yearlycredithrs,
            termsinyear,
            portion,
            autobuildbin,
            isyearrec,
            periods_per_day,
            days_per_cycle,
            attendance_calculation_code,
            sterms,
            suppresspublicview,
            whomodifiedid,
            fiscal_year,
            term,
            term_start_date,
            term_end_date,
            semester,
            is_current_term,
            schoolid,
            yearid,
            _dbt_source_project,
            academic_year,
        from {{ ref("int_powerschool__terms_spine") }}

        union all

        select
            _dbt_source_relation,
            cast(null as int64) as dcid,
            `name`,
            firstday,
            lastday,
            abbreviation,
            cast(null as string) as importmap,
            cast(null as string) as terminfo_guid,
            cast(null as string) as psguid,
            cast(null as string) as ip_address,
            cast(null as string) as whomodifiedtype,
            cast(null as timestamp) as transaction_date,
            cast(null as int64) as id,
            cast(null as int64) as noofdays,
            cast(null as float64) as yearlycredithrs,
            cast(null as int64) as termsinyear,
            cast(null as int64) as portion,
            cast(null as int64) as autobuildbin,
            isyearrec,
            cast(null as int64) as periods_per_day,
            cast(null as int64) as days_per_cycle,
            cast(null as int64) as attendance_calculation_code,
            cast(null as int64) as sterms,
            cast(null as int64) as suppresspublicview,
            cast(null as int64) as whomodifiedid,
            fiscal_year,
            term,
            term_start_date,
            term_end_date,
            semester,
            is_current_term,
            schoolid,
            yearid,
            _dbt_source_project,
            academic_year,
        from focus_conformed
    )

select
    u._dbt_source_relation,
    u.dcid,
    u.`name`,
    u.firstday,
    u.lastday,
    u.abbreviation,
    u.importmap,
    u.terminfo_guid,
    u.psguid,
    u.ip_address,
    u.whomodifiedtype,
    u.transaction_date,
    u.id,
    u.noofdays,
    u.yearlycredithrs,
    u.termsinyear,
    u.portion,
    u.autobuildbin,
    u.isyearrec,
    u.periods_per_day,
    u.days_per_cycle,
    u.attendance_calculation_code,
    u.sterms,
    u.suppresspublicview,
    u.whomodifiedid,
    u.fiscal_year,
    u.term,
    u.term_start_date,
    u.term_end_date,
    u.semester,
    u.is_current_term,
    u.schoolid,
    u.yearid,
    u._dbt_source_project,
    u.academic_year,

    c.first_day_school_year,
    c.last_day_school_year,
    c.days_in_term,

    greatest(u.term_start_date, c.first_day_school_year) as term_start_date_clamped,
    least(u.term_end_date, c.last_day_school_year) as term_end_date_clamped,
from terms_union as u
left join
    term_calendar as c
    on u._dbt_source_project = c._dbt_source_project
    and u.academic_year = c.academic_year
    and u.schoolid = c.schoolid
    and u.term = c.term
