with
    -- Focus's own school_id is its internal id (14, 15, 58...), not the network
    -- school number, and it is a different value from the "school_number" the
    -- focus package itself exposes (a Florida school code like 2008A). Resolve
    -- through both hops, matching int_focus__schools_conformed.
    schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    -- Progress periods have no PowerSchool terms equivalent and are dropped.
    -- The remaining year, semester, and quarter rows match the archive's own
    -- 1 year + 2 semester + 4 quarter rows per school per year.
    marking_periods as (
        select
            mp._dbt_source_project,
            mp.type,
            mp.title,
            mp.short_name,
            mp.start_date,
            mp.end_date,
            mp.syear as academic_year,

            sc.schoolid,

            if(mp.short_name in ('Q1', 'Q2'), 'S1', 'S2') as quarter_semester,

            current_date('{{ var("local_timezone") }}')
            between mp.start_date and mp.end_date as is_within_dates,
        from {{ ref("stg_focus__marking_periods") }} as mp
        inner join schools as sc on mp.school_id = sc.focus_school_id
        where mp.type in ('year', 'semester', 'quarter')
    )

select
    _dbt_source_project,
    schoolid,
    academic_year,

    title as `name`,
    short_name as abbreviation,
    start_date as firstday,
    end_date as lastday,

    -- yearid and fiscal_year have no Focus source. Both are verified,
    -- deterministic network-wide formulas from academic_year (yearid = year -
    -- 1990, fiscal_year = year + 1, confirmed against every PowerSchool
    -- district and year in prod) -- not a guess at an unknown mapping.
    academic_year - 1990 as yearid,
    academic_year + 1 as fiscal_year,

    if(`type` = 'quarter', short_name, null) as term,
    if(`type` = 'quarter', start_date, null) as term_start_date,
    if(`type` = 'quarter', end_date, null) as term_end_date,
    if(`type` = 'quarter', quarter_semester, null) as semester,
    if(`type` = 'quarter', is_within_dates, null) as is_current_term,
from marking_periods
