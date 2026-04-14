with
    locations as (
        select distinct
            location_powerschool_school_id,
            location_dagster_code_location,
            location_clean_name,
        from {{ ref("int_people__location_crosswalk") }}
        where
            not location_is_pathways
            and location_clean_name <> 'KIPP Whittier Elementary'
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

    {{ dbt_utils.generate_surrogate_key(["loc.location_clean_name"]) }} as location_key,

    sec.sections_section_number as section_number,
    sec.sections_expression as period,
    sec.sections_room as room,

from {{ ref("base_powerschool__sections") }} as sec
left join
    locations as loc
    on sec.sections_schoolid = loc.location_powerschool_school_id
    and {{ extract_code_location("sec") }} = loc.location_dagster_code_location
