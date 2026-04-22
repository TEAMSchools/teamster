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
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on sec.sections_schoolid = rt.school_id
    and rt.type = 'RT'
    and sec.terms_lastday >= rt.start_date
    and sec.terms_firstday <= rt.end_date
    and initcap(regexp_extract(sec._dbt_source_relation, r'kipp(\w+)_')) = rt.region
