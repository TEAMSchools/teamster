with
    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    college_assessments_raw as (
        select
            student_number,
            academic_year,
            test_date,
            scope,
            subject_area,
            score_type,
            scale_score,
            administration_round,
            rn_highest,
            max_scale_score,
            superscore,
            running_max_scale_score,
            test_type,

            cast(null as numeric) as percent_correct,

            'college' as score_source,
        from {{ ref("int_assessments__college_assessment") }}
    ),

    college_assessments as (
        {{
            dbt_utils.deduplicate(
                relation="college_assessments_raw",
                partition_by="student_number, score_type, test_date, rn_highest",
                order_by="scale_score desc",
            )
        }}
    ),

    -- Practice (mock SAT/ACT through Illuminate). One row per student x
    -- (scope, test_date, administration_round). Inputs scoped to the
    -- response_type='group' grain of int_assessments__college_assessment_practice.
    practice_assessments as (
        select
            powerschool_student_number as student_number,
            academic_year,
            test_date,
            scope,
            subject_area,
            scale_score,
            administration_round,
            test_type,

            row_number() over (
                partition by powerschool_student_number, scope
                order by scale_score desc, test_date desc
            ) as rn_highest,
        from {{ ref("int_assessments__college_assessment_practice") }}
    ),

    ap_assessments as (
        select
            powerschool_student_number as student_number,
            academic_year,
            test_subject,
            exam_score,
            test_name,
            ps_ap_course_subject_code,
            ap_course_name,
            `data_source`,
            rn_highest,

            'ap' as score_source,
        from {{ ref("int_assessments__ap_assessments") }}
    )

/* college entrance Official (SAT, ACT, PSAT) */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "ca.student_number",
                "ca.score_type",
                "ca.test_date",
                "ca.rn_highest",
                "ca.test_type",
            ]
        )
    }} as assessment_score_key,

    if(
        ca.student_number is not null,
        {{ dbt_utils.generate_surrogate_key(["ca.student_number"]) }},
        cast(null as string)
    ) as student_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'college'",
                "ca.score_type",
                "ca.test_date",
                "ca.academic_year",
                "cast(null as string)",
                "ca.administration_round",
                "cast(null as int64)",
                "ca.test_type",
            ]
        )
    }} as assessment_administration_key,

    ca.test_date as test_date_key,

    ca.scale_score,
    ca.rn_highest as `rank`,
    ca.max_scale_score,
    ca.superscore,
    ca.running_max_scale_score,

    cast(null as string) as proficiency_level,
from college_assessments as ca

union all

/* college entrance Practice (mock SAT/ACT) */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "pa.student_number",
                "pa.scope",
                "pa.test_date",
                "pa.rn_highest",
                "pa.test_type",
            ]
        )
    }} as assessment_score_key,

    {{ dbt_utils.generate_surrogate_key(["pa.student_number"]) }} as student_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'college'",
                "pa.scope",
                "pa.test_date",
                "pa.academic_year",
                "cast(null as string)",
                "pa.administration_round",
                "cast(null as int64)",
                "pa.test_type",
            ]
        )
    }} as assessment_administration_key,

    pa.test_date as test_date_key,

    cast(pa.scale_score as numeric) as scale_score,

    pa.rn_highest as `rank`,

    cast(null as numeric) as max_scale_score,
    cast(null as numeric) as superscore,
    cast(null as numeric) as running_max_scale_score,

    cast(null as string) as proficiency_level,
from practice_assessments as pa

union all

/* AP exams */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "ap.student_number",
                "ap.ap_course_name",
                "ap.academic_year",
                "ap.rn_highest",
            ]
        )
    }} as assessment_score_key,

    if(
        ap.student_number is not null,
        {{ dbt_utils.generate_surrogate_key(["ap.student_number"]) }},
        cast(null as string)
    ) as student_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'ap'",
                "ap.ps_ap_course_subject_code",
                "cast(null as date)",
                "ap.academic_year",
                "cast(null as string)",
                "cast(null as string)",
                "cast(null as int64)",
                "cast(null as string)",
            ]
        )
    }} as assessment_administration_key,

    cast(null as date) as test_date_key,

    cast(ap.exam_score as numeric) as scale_score,

    ap.rn_highest as `rank`,

    cast(null as numeric) as max_scale_score,
    cast(null as numeric) as superscore,
    cast(null as numeric) as running_max_scale_score,

    case
        when ap.exam_score >= 3 then 'Qualified' else 'Not Qualified'
    end as proficiency_level,
from ap_assessments as ap
