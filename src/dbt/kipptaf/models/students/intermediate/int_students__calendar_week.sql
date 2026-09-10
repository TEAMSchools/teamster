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
        -- One row. See int_students__sis_cutover for why the boundary is a
        -- floor derived from recorded attendance rather than from Focus row
        -- presence: int_focus__calendar_week reaches back to AY2010, so
        -- scoping on the years it contains would replace most of Miami's
        -- calendar-week history with a thinner copy. Required, not
        -- belt-and-braces: without it Focus's AY2010 through AY2025 calendar
        -- weeks land beside PowerSchool's real rows for the same Miami
        -- school-weeks and break this model's grain test.
        cross join {{ ref("int_students__sis_cutover") }} as c
        where cw.academic_year >= c.focus_start_academic_year
    )

-- The frozen PowerSchool archive ends at AY2025 (rebuilt with that bound,
-- #5012), so every archive row is a pre-Focus year and needs no cutover
-- predicate. The Focus branch above still floors at the cutover year.
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
