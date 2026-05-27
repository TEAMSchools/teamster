with
    /* The scaffold's `academic_year` is `academic_year_clean` (+1 vs raw)
       which doesn't match the value hashed into
       `dim_assessment_administrations.assessment_administration_key`.
       Re-join to int_assessments__assessments to recover the raw
       `academic_year`. The canonical_* columns also flow from this join. */
    expectations as (
        select
            sc.cc_dcid,
            sc.cc_source_project,
            sc.assessment_id,
            sc.administered_at,
            sc._dbt_source_project,

            a.module_code,
            a.academic_year,
            a.canonical_assessment_id,
            a.canonical_administered_at,
        from {{ ref("int_assessments__scaffold") }} as sc
        inner join
            {{ ref("int_assessments__assessments") }} as a
            on sc.assessment_id = a.assessment_id
        -- ES Writing and other NULL-cc_dcid rows are excluded here because
        -- cc_dcid + _dbt_source_project form the student_section_enrollment_key
        -- and NULL cc_dcid would collide on the placeholder hash. Those rows
        -- live in bridge_assessment_expectations_student_scoped instead.
        where
            sc.is_internal_assessment
            and not sc.is_replacement
            and sc.cc_dcid is not null
            and sc.cc_source_project is not null
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["cc_dcid", "cc_source_project", "assessment_id", "administered_at"]
        )
    }} as assessment_expectation_key,

    {{ dbt_utils.generate_surrogate_key(["cc_dcid", "cc_source_project"]) }}
    as student_section_enrollment_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'illuminate'",
                "module_code",
                "cast(canonical_administered_at as date)",
                "academic_year",
                "_dbt_source_project",
                "null",
                "canonical_assessment_id",
                "null",
            ]
        )
    }} as assessment_administration_key,
from expectations
