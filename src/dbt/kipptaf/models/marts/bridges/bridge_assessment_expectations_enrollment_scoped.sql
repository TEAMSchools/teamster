with
    /* The scaffold's `academic_year` is `academic_year_clean` (+1 vs raw)
       which doesn't match the value hashed into
       `dim_assessment_administrations.assessment_administration_key`.
       Re-join to int_assessments__assessments to recover the raw
       `academic_year`. The canonical_* columns also flow from this join. */
    expectations as (
        select
            sc.cc_dcid,
            sc.cc_source_relation,
            sc.assessment_id,
            sc.administered_at,
            sc.region,

            a.module_code,
            a.academic_year,
            a.canonical_assessment_id,
            a.canonical_administered_at,
        from {{ ref("int_assessments__scaffold") }} as sc
        inner join
            {{ ref("int_assessments__assessments") }} as a
            on sc.assessment_id = a.assessment_id
        -- ES Writing rows in int_assessments__course_enrollments synthesize
        -- NULL cc_dcid (no PowerSchool course-enrollment record exists for
        -- those students). Excluded here because cc_dcid + cc_source_relation
        -- form the student_section_enrollment_key — NULL inputs would all hash
        -- to the same generate_surrogate_key placeholder and collide on the PK.
        where
            sc.is_internal_assessment
            and not sc.is_replacement
            and sc.cc_dcid is not null
            and sc.cc_source_relation is not null
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["cc_dcid", "cc_source_relation", "assessment_id", "administered_at"]
        )
    }} as assessment_expectation_key,

    {{ dbt_utils.generate_surrogate_key(["cc_dcid", "cc_source_relation"]) }}
    as student_section_enrollment_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'illuminate'",
                "module_code",
                "cast(canonical_administered_at as date)",
                "academic_year",
                "region",
                "cast(null as string)",
                "canonical_assessment_id",
                "cast(null as string)",
            ]
        )
    }} as assessment_administration_key,
from expectations
