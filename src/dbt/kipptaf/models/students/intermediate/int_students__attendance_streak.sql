with
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
        -- One row. See int_students__sis_cutover for why the boundary is a
        -- floor derived from recorded attendance rather than from Focus row
        -- presence. Required, not belt-and-braces: without it Focus's AY2020
        -- rows would land beside PowerSchool's real AY2020-AY2025 rows for
        -- Miami and break this model's own grain test.
        cross join {{ ref("int_students__sis_cutover") }} as c
        where fa.academic_year >= c.focus_start_academic_year
    )

-- The frozen PowerSchool archive ends at AY2025 (rebuilt with that bound,
-- #5012), so every archive row is a pre-Focus year and needs no cutover
-- predicate. The Focus branch above still floors at the cutover year.
select
    _dbt_source_relation,
    studentid,
    student_number,
    yearid,
    att_code,
    streak_id,
    streak_start_date,
    streak_end_date,
    streak_length_membership,
    streak_length_calendar,
    _dbt_source_project,

    yearid + 1990 as academic_year,
from {{ ref("int_powerschool__attendance_streak") }}

union all

select
    _dbt_source_relation,
    studentid,
    student_number,
    yearid,
    att_code,
    streak_id,
    streak_start_date,
    streak_end_date,
    streak_length_membership,
    streak_length_calendar,
    _dbt_source_project,
    academic_year,
from focus_conformed
