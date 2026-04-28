with
    locations as (
        select powerschool_school_id, dagster_code_location, location_name,
        from {{ ref("stg_google_sheets__people__locations") }}
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["sec.sections_dcid", "sec._dbt_source_relation"]
        )
    }} as course_section_key,

    {{
        dbt_utils.generate_surrogate_key(
            ["sec.courses_course_number", "sec._dbt_source_relation"]
        )
    }} as course_key,

    {{ dbt_utils.generate_surrogate_key(["loc.location_name"]) }} as location_key,

    sec.sections_section_number as identifier,
    sec.sections_expression as period,
    sec.sections_room as room,

from {{ ref("base_powerschool__sections") }} as sec
left join
    locations as loc
    on sec.sections_schoolid = loc.powerschool_school_id
    and {{ extract_code_location("sec") }} = loc.dagster_code_location
