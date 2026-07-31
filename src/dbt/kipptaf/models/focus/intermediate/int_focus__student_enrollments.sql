with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_focus", "int_focus__student_enrollment"),
                ]
            )
        }}
    ),

    with_source_project as (
        select
            *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
        from union_relations
    ),

    enrollments as (
        select *, {{ extract_region("with_source_project") }} as region,
        from with_source_project
    )

select
    e.* except (
        school_number, school_title, school_state_school_id, grade_level_short_name
    ),

    loc.powerschool_school_id as ps_schoolid,
    loc.location_name as school,
    loc.abbreviation as school_abbreviation,
    loc.reporting_school_id as reporting_schoolid,
    loc.location_region as region_official_name,
    loc.deanslist_school_id,

    'KTAF' as district,

    concat(e.region, e.school_level) as region_school_level,

from enrollments as e
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on e.school_number = loc.focus_school_id
