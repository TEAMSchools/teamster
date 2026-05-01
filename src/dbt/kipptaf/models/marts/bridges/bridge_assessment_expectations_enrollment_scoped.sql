with
    /* The scaffold's `grade_level_id` and `academic_year` columns are
       transformed (`coalesce(illuminate_grade_level_id, agl.grade_level_id)`
       and `academic_year_clean` respectively) and don't match the values
       hashed into `dim_assessment_administrations.assessment_administration_key`,
       which uses the raw `grade_level` and `academic_year` from
       int_assessments__assessments. Re-join to int_assessments__assessments
       to recover the canonical hash inputs. */
    expectations as (
        select
            sc.cc_dcid,
            sc.cc_source_relation,
            sc.assessment_id,
            sc.administered_at,
            sc.region,

            a.title,
            a.subject_area,
            a.scope,
            a.module_code,
            a.grade_level,
            a.academic_year,
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
                "title",
                "subject_area",
                "scope",
                "module_code",
                "grade_level",
                "cast(administered_at as date)",
                "academic_year",
                "cast(null as string)",
                "region",
                "cast(null as string)",
                "cast(null as string)",
            ]
        )
    }} as assessment_administration_key,
from expectations
