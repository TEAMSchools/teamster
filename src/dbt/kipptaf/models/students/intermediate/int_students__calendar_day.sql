with
    -- Focus's school_id is its internal id (14, 15, 58...), not the network
    -- school number, and it differs from the "school_number" the focus package
    -- exposes (a Florida code like 2332A). Resolve through both hops. The inner
    -- join is also the filter that drops Focus's three non-instructional schools
    -- (Applicants, Virtual Franchise, ZZ Course History), which have no
    -- locations row.
    focus_schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    -- One row. See int_students__sis_cutover for why the boundary is a floor
    -- derived from recorded attendance rather than from Focus row presence:
    -- int_focus__calendar_day reaches back to AY2010 with 3 schools against
    -- PowerSchool's 6, so scoping on the years it contains would replace most of
    -- Miami's calendar history with a thinner copy.
    cutover as (
        select focus_start_academic_year, from {{ ref("int_students__sis_cutover") }}
    ),

    -- The frozen PowerSchool archive keeps serving Miami for every year Focus
    -- does not cover. Scoping by year rather than by project is what preserves
    -- Miami AY2020 through AY2025.
    --
    -- Dual-exposes the neutral (school_date, academic_year, is_in_session,
    -- is_in_membership) alongside the legacy names (date_value, yearid,
    -- insession, membershipvalue) that dim_school_calendars and the NJ-parity
    -- gate read. See "Dual-exposed names" in the plan.
    powerschool_conformed as (
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

            t.yearid,
            t.yearid + 1990 as academic_year,

            cd.insession = 1 as is_in_session,
            cd.membershipvalue > 0 as is_in_membership,
        from {{ ref("stg_powerschool__calendar_day") }} as cd
        inner join
            {{ ref("stg_powerschool__terms") }} as t
            on cd.schoolid = t.schoolid
            and cd.date_value between t.firstday and t.lastday
            and cd._dbt_source_project = t._dbt_source_project
            and t.isyearrec = 1
        cross join cutover as c
        where
            not (
                cd._dbt_source_project = 'kippmiami'
                and t.yearid >= c.focus_start_academic_year - 1990
            )
    ),

    -- int_focus__calendar_day is Focus-native: it emits academic_year and
    -- school_date, and no insession or membershipvalue at all. A row existing there
    -- IS an in-session day, so both flags are constants supplied here.
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
            cd.academic_year - 1990 as yearid,

            1 as insession,
            cast(1 as float64) as membershipvalue,
            true as is_in_session,
            true as is_in_membership,
        from {{ ref("int_focus__calendar_day") }} as cd
        inner join focus_schools as fs on cd.schoolid = fs.focus_school_id
        cross join cutover as c
        -- Required, not belt-and-braces. Without it Focus's AY2010 through AY2025
        -- calendar rows land beside PowerSchool's real rows for the same Miami
        -- school-days and break this model's own grain test.
        where cd.academic_year >= c.focus_start_academic_year
    )

-- `full union all corresponding` matches columns by NAME. A plain `union all`
-- matches by POSITION, and the two CTEs above list schoolid in different
-- positions, which would silently align schoolid with insession.
select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
