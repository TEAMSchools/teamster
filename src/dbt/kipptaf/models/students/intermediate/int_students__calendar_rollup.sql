with
    -- Focus's school_id is its internal id (14, 15, 58...), not the network
    -- school number. The inner join is also the filter that drops Focus's
    -- non-instructional schools, which have no locations row.
    focus_schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    -- One row. See int_students__sis_cutover for why the boundary is a floor
    -- derived from recorded attendance rather than from Focus row presence.
    cutover as (
        select focus_start_academic_year, from {{ ref("int_students__sis_cutover") }}
    ),

    -- The frozen PowerSchool archive keeps serving Miami for every year Focus
    -- does not cover. Scoping by year rather than by project is what preserves
    -- Miami AY2020 through AY2025. Star qualified to the aliased relation --
    -- an unqualified `select *,` would leak the cross-joined cutover CTE's
    -- focus_start_academic_year into the output via `full union all
    -- corresponding` null-filling it on the focus_conformed side.
    powerschool_conformed as (
        select cr.*,
        from {{ ref("int_powerschool__calendar_rollup") }} as cr
        cross join cutover as c
        where
            not (
                cr._dbt_source_project = 'kippmiami'
                and cr.yearid >= c.focus_start_academic_year - 1990
            )
    ),

    -- int_focus__calendar_rollup is Focus-native: academic_year, min_school_date
    -- and max_school_date, and no track column at all. track is supplied here
    -- as a typed NULL, which is what the consuming join is made null-safe for.
    focus_conformed as (
        select
            cr.days_total,
            cr.days_remaining,

            -- Carried through explicitly: the ops dashboard and csgf extract
            -- both join on _dbt_source_project.
            cr._dbt_source_relation,
            cr._dbt_source_project,

            fs.schoolid,

            cr.academic_year - 1990 as yearid,
            cr.min_school_date as min_calendardate,
            cr.max_school_date as max_calendardate,

            cast(null as string) as track,
        from {{ ref("int_focus__calendar_rollup") }} as cr
        inner join focus_schools as fs on cr.schoolid = fs.focus_school_id
        cross join cutover as c
        -- Required, not belt-and-braces. Without it Focus's pre-cutover rows
        -- would land beside PowerSchool's real rows for the same Miami
        -- school-years and break this model's own grain test.
        where cr.academic_year >= c.focus_start_academic_year
    )

-- `full union all corresponding` matches columns by NAME. A plain `union all`
-- matches by POSITION, and the two CTEs above list schoolid/yearid in
-- different positions, which would silently misalign columns.
select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
