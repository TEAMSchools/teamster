with
    scaffold as (
        select
            s.powerschool_student_number,
            s.assessment_id,
            s.title,
            s.subject_area,
            s.academic_year,
            s.administered_at,
            s.scope,
            s.module_type,
            s.module_code,
            s.grade_level_id,
            s.powerschool_school_id,
            s.region,
            s.is_internal_assessment,
        from {{ ref("int_assessments__scaffold") }} as s
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "sc.powerschool_student_number",
                "sc.assessment_id",
                "sc.administered_at",
            ]
        )
    }} as student_assessment_expectation_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'illuminate'",
                "sc.title",
                "sc.subject_area",
                "sc.scope",
                "sc.module_code",
                "cast(sc.grade_level_id as int64)",
            ]
        )
    }} as assessment_key,

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

    if(
        sc.powerschool_student_number is not null,
        {{ dbt_utils.generate_surrogate_key(["sc.powerschool_student_number"]) }},
        cast(null as string)
    ) as student_key,

    sc.academic_year,
    sc.administered_at as administered_date,
    sc.is_internal_assessment,
from scaffold as sc
left join
    {{ ref("stg_google_sheets__reporting__terms") }} as rt
    on sc.administered_at between rt.start_date and rt.end_date
    and sc.powerschool_school_id = rt.school_id
    and sc.region = rt.region
    and rt.type = 'RT'
