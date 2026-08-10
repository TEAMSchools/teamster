with
    -- Focus's own school_id is its internal id (14, 15, 58...), not the
    -- network school number, and it is a different value from the
    -- "school_number" the focus package itself exposes (a Florida school code
    -- like 2008A). Resolve through both hops, matching the Focus branch of
    -- int_students__schools.
    focus_schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    -- quarter_semester and is_within_dates are derived in
    -- stg_focus__marking_periods; this model only resolves Focus's internal
    -- school id to the network one and applies the filters below.
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
        -- Progress periods have no PowerSchool terms equivalent. The 2018
        -- floor is Miami's first school year: Focus carries a full
        -- year/semester/quarter set for two schools in every syear back to
        -- 1980, which would fabricate history here. Both filters stay in this
        -- model rather than in staging -- 321 report card grade rows point at
        -- pre-2018 marking periods, so flooring the staging model orphans
        -- them.
        where mp.type in ('year', 'semester', 'quarter') and mp.syear >= 2018
    ),

    -- Miami school-year, semester, and quarter definitions from Focus,
    -- conformed to the PowerSchool terms vocabulary so they merge into the
    -- network terms spine below by column name (full union all
    -- corresponding). yearid and fiscal_year have no Focus source and are
    -- derived from the verified network-wide formulas (yearid = academic_year
    -- - 1990, fiscal_year = academic_year + 1). term, term_start_date,
    -- term_end_date, semester, and is_current_term are populated only for
    -- quarter rows, matching the quarter-only grain the former
    -- int_powerschool__terms consumers expect -- they filter this model to
    -- term is not null at the call site instead of a second conform model.
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

    -- int_powerschool__terms resolves quarter dates and codes through termbins
    -- rather than the terms table's own quarter rows -- the two disagree on
    -- dates for some schools (termbins carries the actual in-session start
    -- date; the raw quarter row often defaults to a placeholder). termbins is
    -- what every existing quarter-grain consumer already reads, so its columns
    -- are attached to the matching raw terms row below rather than recomputed
    -- from firstday / lastday.
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

    -- A small number of historical quarters (a handful of non-instructional
    -- schoolids, mostly pre-2018) exist in int_powerschool__terms via its
    -- termbins join but have no corresponding Q1-Q4 row in the raw terms
    -- table at all -- verified against prod (kippnewark/kippcamden schoolids
    -- 73252, 73253, 133570965, 179902). A left join from the raw side would
    -- silently drop those quarters' dates entirely. Full join instead, so an
    -- unmatched quarter survives as its own row (every raw-only column
    -- null-fills, matching a row Focus never carried).
    powerschool_joined as (
        select
            p.* except (
                semester, rn, schoolid, yearid, academic_year, _dbt_source_project
            ),

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
    ),

    -- Focus is Miami's system of record for term definitions, so the frozen
    -- archive contributes no Miami rows.
    powerschool_conformed as (
        select *, from powerschool_joined where _dbt_source_project != 'kippmiami'
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
