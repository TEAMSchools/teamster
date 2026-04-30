with
    unnested as (
        select
            a.title,
            a.subject_area,
            a.scope,
            a.module_code,
            a.grade_level,

            cast(a.administered_at as date) as administered_date,
            a.academic_year,
            region,
        from {{ ref("int_assessments__assessments") }} as a
        cross join unnest(a.regions_assessed_array) as region
        where a.is_internal_assessment
    )

    {{
        dbt_utils.deduplicate(
            relation="unnested",
            partition_by=(
                "title, subject_area, scope, module_code, grade_level, "
                "administered_date, academic_year, region"
            ),
            order_by="title",
        )
    }}
