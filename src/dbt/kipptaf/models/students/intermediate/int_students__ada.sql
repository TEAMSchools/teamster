with
    -- int_focus__ada is Focus-native: academic_year not yearid, days_in_session
    -- not days_in_membership, days_absent not days_absent_unexcused, and no
    -- studentid. Focus does not model the excused/unexcused split at this
    -- grain, so days_absent maps onto the legacy days_absent_unexcused name --
    -- see that column's description for the semantic gap this creates.
    focus_conformed as (
        select
            fa.student_number,
            fa.academic_year,
            fa.days_present,
            fa.ada,
            fa.days_in_session as days_in_membership,
            fa.days_absent as days_absent_unexcused,

            -- Carried through explicitly: every downstream join keys on
            -- _dbt_source_project, so letting it null-fill would break the
            -- Miami joins.
            fa._dbt_source_relation,
            fa._dbt_source_project,

            cast(null as int64) as studentid,

            fa.academic_year - 1990 as yearid,
        from {{ ref("int_focus__ada") }} as fa
        -- One row. See int_students__sis_cutover for why the boundary is a
        -- floor derived from recorded attendance rather than from Focus row
        -- presence. Required, not belt-and-braces: without it Focus's AY2020
        -- rows would land beside PowerSchool's real AY2020-AY2025 rows for
        -- Miami and break this model's own grain test.
        cross join {{ ref("int_students__sis_cutover") }} as c
        where fa.academic_year >= c.focus_start_academic_year
    )

-- `full union all corresponding` matches columns by NAME. A plain `union all`
-- matches by POSITION, and the two CTEs above list columns in different
-- positions, which would silently misalign them.
-- The frozen PowerSchool archive ends at AY2025 (rebuilt with that bound,
-- #5012), so every archive row is a pre-Focus year and needs no cutover
-- predicate. The Focus branch above still floors at the cutover year.
select *,
from {{ ref("int_powerschool__ada") }}

full union all corresponding

select *,
from focus_conformed
