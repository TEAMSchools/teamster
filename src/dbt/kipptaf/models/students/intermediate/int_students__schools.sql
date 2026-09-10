with
    focus_conformed as (
        select
            s._dbt_source_relation,
            s._dbt_source_project,
            s.title as `name`,

            loc.location_key,
            loc.abbreviation,
            loc.powerschool_school_id as school_number,

            s.school_level,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    )

select *,
from {{ ref("stg_powerschool__schools") }}

full union all corresponding

select *,
from focus_conformed
