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
    -- derived from recorded attendance rather than from Focus row presence:
    -- int_focus__calendar_week reaches back to AY2010, so scoping on the
    -- years it contains would replace most of Miami's calendar-week history
    -- with a thinner copy.
    cutover as (
        select focus_start_academic_year, from {{ ref("int_students__sis_cutover") }}
    ),

    -- The frozen PowerSchool archive ends at AY2025 (rebuilt with that bound,
    -- #5012), so every archive row is a pre-Focus year and needs no cutover
    -- predicate. The Focus branch below still floors at the cutover year.
    powerschool_conformed as (
        select cw.*, from {{ ref("int_powerschool__calendar_week") }} as cw
    ),

    -- int_focus__calendar_week is Focus-native: it emits academic_year but no
    -- yearid or region, and schoolid is Focus's internal id rather than the
    -- network school number.
    focus_conformed as (
        select
            cw.* except (schoolid, academic_year),

            fs.schoolid,

            cw.academic_year,
            cw.academic_year - 1990 as yearid,

            {{ extract_region("cw") }} as region,
        from {{ ref("int_focus__calendar_week") }} as cw
        inner join focus_schools as fs on cw.schoolid = fs.focus_school_id
        cross join cutover as c
        -- Required, not belt-and-braces. Without it Focus's AY2010 through
        -- AY2025 calendar weeks land beside PowerSchool's real rows for the
        -- same Miami school-weeks and break this model's grain test.
        where cw.academic_year >= c.focus_start_academic_year
    )

-- `full union all corresponding` matches columns by NAME. A plain `union all`
-- matches by POSITION, and the two CTEs above list schoolid/yearid in
-- different positions, which would silently misalign columns.
select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
