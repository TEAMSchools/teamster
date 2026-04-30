/* This bridge covers K-8 replacement-curriculum scheduled administrations
   (the `is_replacement` branch of int_assessments__scaffold). It does NOT
   currently cover the non-internal scaffold branch (state / college / AP):
   that branch sources from int_assessments__assessments and represents
   teacher-created Illuminate items that are not surfaced in
   dim_assessment_administrations (the dim's state / college / AP rows come
   from int_pearson__all_assessments / int_fldoe__all_assessments /
   int_assessments__college_assessment / int_assessments__ap_assessments,
   which the scaffold has no upstream linkage to). Including those rows
   would produce 100% orphans against dim_assessment_administrations.

   Hash inputs mirror the illuminate branch of dim_assessment_administrations
   exactly: re-join int_assessments__assessments to recover the canonical
   `grade_level` and `academic_year` (the scaffold's `grade_level_id` is
   illuminate-indexed and the scaffold's `academic_year` is
   `academic_year_clean`, neither of which match the dim's hash inputs). */
with
    expectations as (
        select
            sc.powerschool_student_number,
            sc.assessment_id,
            sc.administered_at,
            sc.region,
            sc.powerschool_school_id,

            a.title,
            a.subject_area,
            a.scope,
            a.module_code,
            a.grade_level,
            a.academic_year,

            rt.code as term_code,
            rt.type as term_type,
            rt.name as term_name,
            rt.start_date as term_start_date,
            rt.region as term_region,
            rt.school_id as term_school_id,
        from {{ ref("int_assessments__scaffold") }} as sc
        inner join
            {{ ref("int_assessments__assessments") }} as a
            on sc.assessment_id = a.assessment_id
        left join
            {{ ref("stg_google_sheets__reporting__terms") }} as rt
            on sc.administered_at between rt.start_date and rt.end_date
            and sc.powerschool_school_id = rt.school_id
            and sc.region = rt.region
            and rt.type = 'RT'
        where sc.is_replacement and sc.powerschool_student_number is not null
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["powerschool_student_number", "assessment_id", "administered_at"]
        )
    }} as assessment_expectation_key,

    {{ dbt_utils.generate_surrogate_key(["powerschool_student_number"]) }}
    as student_key,

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

    if(
        term_code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "term_type",
                    "term_code",
                    "term_name",
                    "term_start_date",
                    "term_region",
                    "term_school_id",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,
from expectations
