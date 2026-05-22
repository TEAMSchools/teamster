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

    sch.location_key,

    sec.sections_section_number as identifier,
    sec.sections_expression as period,
    sec.sections_room as room,

from {{ ref("base_powerschool__sections") }} as sec
left join
    {{ ref("stg_powerschool__schools") }} as sch
    on sec.sections_schoolid = sch.school_number
    and sec._dbt_source_project = sch._dbt_source_project
