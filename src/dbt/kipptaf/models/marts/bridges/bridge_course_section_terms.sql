with
    code_locations as (
        {{
            dbt_utils.deduplicate(
                relation=ref("stg_google_sheets__people__locations"),
                partition_by="city",
                order_by="(dagster_code_location = 'kipptaf') asc, powerschool_school_id desc",
            )
        }}
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["sec.sections_dcid", "sec._dbt_source_relation"]
        )
    }} as course_section_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "rt.type",
                "rt.code",
                "rt.name",
                "rt.start_date",
                "rt.region",
                "rt.school_id",
            ]
        )
    }} as term_key,

    rt.academic_year,

from {{ ref("base_powerschool__sections") }} as sec
inner join code_locations as cl on cl.dagster_code_location = sec._dbt_source_project
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on sec.sections_schoolid = rt.school_id
    and rt.type = 'RT'
    and sec.terms_lastday >= rt.start_date
    and sec.terms_firstday <= rt.end_date
    and rt.region = cl.city
