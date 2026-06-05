with
    members_unnested as (
        select
            a.assessment_id as member_assessment_id,
            a.canonical_assessment_id,
            a.module_code,
            a.academic_year,

            c.administered_date as canonical_administered_date,

            region,

            concat('kipp', lower(region)) as _dbt_source_project,
        from {{ ref("int_assessments__assessments_members") }} as a
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on a.canonical_assessment_id = c.canonical_assessment_id
        cross join unnest(a.regions_assessed_array) as region
        where a.is_internal_assessment
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "'illuminate'",
                "module_code",
                "canonical_administered_date",
                "academic_year",
                "_dbt_source_project",
                "null",
                "canonical_assessment_id",
                "null",
            ]
        )
    }} as assessment_administration_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'illuminate'",
                "module_code",
                "member_assessment_id",
                "null",
            ]
        )
    }} as assessment_key,
from members_unnested
