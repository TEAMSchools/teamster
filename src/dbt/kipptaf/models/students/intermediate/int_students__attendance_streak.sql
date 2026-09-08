with
    -- One row. See int_students__sis_cutover for why the boundary is a floor
    -- derived from recorded attendance rather than from Focus row presence.
    cutover as (
        select focus_start_academic_year, from {{ ref("int_students__sis_cutover") }}
    ),

    -- The frozen PowerSchool archive keeps serving Miami for every year Focus
    -- does not cover. Scoping by year rather than by project is what preserves
    -- Miami AY2020 through AY2025.
    powerschool_conformed as (
        select ps.*, ps.yearid + 1990 as academic_year,
        from {{ ref("int_powerschool__attendance_streak") }} as ps
        cross join cutover as c
        where
            not (
                ps._dbt_source_project = 'kippmiami'
                and ps.yearid >= c.focus_start_academic_year - 1990
            )
    ),

    -- `int_focus__attendance_streak` splits the district's overloaded
    -- `att_code` into `streak_type` plus `streak_value`. The 'daily_code'
    -- family carries the actual Focus attendance code, which is null on a
    -- present day. The 'state_value' family carries the stringified
    -- present/absent value. `int_powerschool__attendance_streak` unions the
    -- same 2 families, so both Focus families stay unfiltered here to
    -- reassemble the same district shape. Reassemble the code family's district
    -- labeling too: a present streak has a null `streak_value` because
    -- `daily_code` is null on a present day, and PowerSchool labels it 'P'.
    focus_conformed as (
        select
            fa.student_number,
            fa.streak_id,
            fa.streak_start_date,
            fa.streak_end_date,
            fa.streak_length_days as streak_length_membership,
            fa.streak_length_calendar_days as streak_length_calendar,

            -- Carried through explicitly: fct_student_attendance_streaks joins
            -- on _dbt_source_project and hashes it into
            -- student_attendance_streak_key.
            fa._dbt_source_relation,
            fa._dbt_source_project,

            cast(null as int64) as studentid,

            fa.academic_year,
            fa.academic_year - 1990 as yearid,
            coalesce(fa.streak_value, 'P') as att_code,
        from {{ ref("int_focus__attendance_streak") }} as fa
        cross join cutover as c
        -- Required, not belt-and-braces. Without it Focus's AY2020 rows would
        -- land beside PowerSchool's real AY2020-AY2025 rows for Miami and
        -- break this model's own grain test.
        where fa.academic_year >= c.focus_start_academic_year
    )

-- `full union all corresponding` matches columns by NAME. A plain `union all`
-- matches by POSITION, and the two CTEs above list columns in different
-- positions, which would silently misalign them.
select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
