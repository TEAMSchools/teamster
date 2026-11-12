with
    member_regions as (
        select
            a.source,
            a.assessment_id as member_assessment_id,
            a.module_code,
            a.academic_year,

            rg.region,
            rg.canonical_assessment_id,

            c.administered_date as canonical_administered_date,

            concat('kipp', lower(rg.region)) as _dbt_source_project,
        from {{ ref("int_assessments__assessments_members") }} as a
        inner join
            {{ ref("int_assessments__assessment_region_groups") }} as rg
            on a.source = rg.source
            and a.assessment_id = rg.assessment_id
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on rg.source = c.source
            and rg.canonical_assessment_id = c.canonical_assessment_id
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "source",
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
                "source",
                "module_code",
                "member_assessment_id",
                "null",
            ]
        )
    }} as assessment_key,
from member_regions
