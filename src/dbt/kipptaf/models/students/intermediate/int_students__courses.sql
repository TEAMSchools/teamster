with
    powerschool_conformed as (
        select
            course_number, course_name, credittype, credit_hours, _dbt_source_project,
        from {{ ref("stg_powerschool__courses") }}
    ),

    -- int_focus__courses carries one row per course per school year: 14,616
    -- rows against 1,350 distinct short_name. dim_courses.course_key is unique
    -- on (course_number, _dbt_source_project), so the Focus branch keeps the
    -- most recent year per short_name. The 3 courses with a null short_name
    -- cannot produce a key and are dropped -- no scheduled course period
    -- references one, verified 2026-08-25.
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    focus_courses as (
        select
            syear,
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
                order_by="syear desc",
            )
        }}
    ),

    focus_conformed as (
        -- trunk-ignore(sqlfluff/AM04): deduplicate resolves columns at run time
        select * except (syear), from focus_deduplicated
    )

select *,
from powerschool_conformed

full union all corresponding

select *,
from focus_conformed
