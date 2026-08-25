with
    powerschool_conformed as (
        select
            course_number, course_name, credittype, credit_hours, _dbt_source_project,
        from {{ ref("stg_powerschool__courses") }}
    ),

    -- int_focus__courses is 14,616 rows against only 1,350 distinct non-null
    -- short_name -- more than one row per (short_name, syear) for 518 of them.
    -- dim_courses.course_key is unique on (course_number, _dbt_source_project),
    -- so the Focus branch must pick exactly one row per short_name.
    -- course_id is unique per row (14,616 distinct across 14,616 rows), so
    -- ordering by syear desc, course_id desc fully determines the pick --
    -- syear desc alone leaves a tie (59 of the 137 courses actually referenced
    -- by scheduled Miami course periods tie at their max syear), and
    -- array_agg(... limit 1) has no guaranteed tiebreak in BigQuery without
    -- one. The 3 courses with a null short_name cannot produce a key and are
    -- dropped -- no scheduled course period references one, verified
    -- 2026-08-25.
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    focus_courses as (
        select
            syear,
            course_id,
            short_name as course_number,
            title as course_name,
            credit_hours,

            -- Focus has no credit-type field. Null rather than a guess.
            cast(null as string) as credittype,

            'kippmiami' as _dbt_source_project,
        from {{ ref("int_focus__courses") }}
        where short_name is not null
    ),

    focus_deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation="focus_courses",
                partition_by="course_number",
                order_by="syear desc, course_id desc",
            )
        }}
    ),

    focus_conformed as (
        -- trunk-ignore(sqlfluff/AM04): deduplicate resolves columns at run time
        select * except (syear, course_id), from focus_deduplicated
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
