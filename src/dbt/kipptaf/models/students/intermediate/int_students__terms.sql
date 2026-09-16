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
        -- Progress periods have no PowerSchool `terms` equivalent. The 2018
        -- floor is Miami's first school year: Focus carries a full
        -- year/semester/quarter set for 2 schools in every syear back to 1980,
        -- which would fabricate history here. Both filters stay in this model
        -- rather than in staging, because 321 report card grade rows point at
        -- pre-2018 marking periods and flooring the staging model orphans them.
        where mp.type in ('year', 'semester', 'quarter') and mp.syear >= 2018
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

    powerschool_quarters as (
        select
            schoolid,
            yearid,
            academic_year,
            term,
            term_start_date,
            term_end_date,
            semester,
            is_current_term,
            _dbt_source_project,
        from {{ ref("int_powerschool__terms") }}
    ),

    -- A small number of historical quarters exist in `int_powerschool__terms`
    -- via its `termbins` join but have no corresponding Q1-Q4 row in the raw
    -- `terms` table — a handful of non-instructional schoolids, mostly
    -- pre-2018, verified against prod (kippnewark and kippcamden schoolids
    -- 73252, 73253, 133570965, 179902). A left join from the raw side would
    -- silently drop those quarters' dates. Full join instead, so an unmatched
    -- quarter survives as its own row and every raw-only column null-fills,
    -- which matches a row Focus never carried.
    powerschool_joined as (
        -- Enumerated, not `p.* except`: BigQuery fixes a view's column list at
        -- create time and Dagster rebuilds a view only when its raw SQL
        -- changes, so a `*` here would never pick up a column added upstream.
        select
            p._dbt_source_relation,
            p.dcid,
            p.name,
            p.firstday,
            p.lastday,
            p.abbreviation,
            p.importmap,
            p.terminfo_guid,
            p.psguid,
            p.ip_address,
            p.whomodifiedtype,
            p.transaction_date,
            p.id,
            p.noofdays,
            p.yearlycredithrs,
            p.termsinyear,
            p.portion,
            p.autobuildbin,
            p.isyearrec,
            p.periods_per_day,
            p.days_per_cycle,
            p.attendance_calculation_code,
            p.sterms,
            p.suppresspublicview,
            p.whomodifiedid,
            p.fiscal_year,

            q.term,
            q.term_start_date,
            q.term_end_date,
            q.semester,
            q.is_current_term,

            coalesce(p.schoolid, q.schoolid) as schoolid,
            coalesce(p.yearid, q.yearid) as yearid,
            coalesce(
                p._dbt_source_project, q._dbt_source_project
            ) as _dbt_source_project,
            coalesce(p.academic_year, q.academic_year) as academic_year,
        from {{ ref("stg_powerschool__terms") }} as p
        full join
            powerschool_quarters as q
            on p.schoolid = q.schoolid
            and p.yearid = q.yearid
            and p.abbreviation = q.term
            and p._dbt_source_project = q._dbt_source_project
            and p.rn = 1
    )

select
    _dbt_source_relation,
    dcid,
    name,
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
from powerschool_joined

union all

-- Positional union: this list mirrors the PowerSchool branch column for column,
-- with a typed null where Focus has no equivalent.
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
