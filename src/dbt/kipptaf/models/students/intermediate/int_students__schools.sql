with
    focus_conformed as (
        select
            s._dbt_source_relation,
            s._dbt_source_project,
            s.title as `name`,
            s.school_level,
            s.state as schoolstate,

            loc.powerschool_school_id as school_number,
            loc.location_key,
            loc.abbreviation,

            cast(null as int64) as low_grade,
            cast(null as int64) as high_grade,
            cast(null as string) as schoolcity,
            cast(null as string) as schoolzip,

            if(
                s.exclude_from_state_reporting = 'Y', 1, 0
            ) as state_excludefromreporting,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    )

select
    ps._dbt_source_relation,
    ps._dbt_source_project,
    ps.`name`,
    ps.school_level,
    ps.school_number,

    loc.location_key,

    ps.abbreviation,
    ps.low_grade,
    ps.high_grade,
    ps.schoolcity,
    ps.schoolstate,
    ps.schoolzip,
    ps.state_excludefromreporting,
from {{ ref("stg_powerschool__schools") }} as ps
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on ps.school_number = loc.powerschool_school_id
    and not loc.is_pathways
    and loc.location_name <> 'KIPP Whittier Elementary'

union all

select
    _dbt_source_relation,
    _dbt_source_project,
    `name`,
    school_level,
    school_number,
    location_key,
    abbreviation,
    low_grade,
    high_grade,
    schoolcity,
    schoolstate,
    schoolzip,
    state_excludefromreporting,
from focus_conformed
