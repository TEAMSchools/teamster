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

    sec.sections_dcid,
    rt.code as term_code,
    rt.academic_year,

from {{ ref("base_powerschool__sections") }} as sec
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on sec.sections_schoolid = rt.school_id
    and rt.type = 'RT'
    and rt.start_date <= sec.terms_lastday
    and rt.end_date >= sec.terms_firstday
    and initcap(regexp_extract(sec._dbt_source_relation, r'kipp(\w+)_')) = rt.region
