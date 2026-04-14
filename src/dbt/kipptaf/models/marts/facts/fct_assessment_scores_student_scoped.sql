with
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
            course_discipline,
            rn_highest,
            max_scale_score,
            superscore,
            running_max_scale_score,
            aligned_subject_area,
            aligned_subject,
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

/* college entrance (SAT, ACT, PSAT) */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "ca.student_number",
                "ca.score_type",
                "ca.test_date",
                "ca.rn_highest",
            ]
        )
    }} as assessment_score_key,

    {{ dbt_utils.generate_surrogate_key(["ca.student_number"]) }} as student_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'college'",
                "ca.scope",
                "ca.subject_area",
                "ca.scope",
                "ca.score_type",
                "cast(null as int64)",
            ]
        )
    }} as assessment_key,

    ca.test_date as test_date_key,

    ca.student_number,
    ca.academic_year,
    ca.scope as assessment_scope,
    ca.subject_area,
    ca.score_type,
    ca.scale_score,
    ca.percent_correct,
    ca.administration_round,
    ca.course_discipline,
    ca.test_type,
    ca.rn_highest,
    ca.max_scale_score,
    ca.superscore,
    ca.running_max_scale_score,
    ca.aligned_subject_area,
    ca.aligned_subject,

    cast(null as string) as proficiency_level,

    ca.score_source,
from college_assessments as ca

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

    {{ dbt_utils.generate_surrogate_key(["ap.student_number"]) }} as student_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'college'",
                "concat('AP ', ap.test_subject)",
                "ap.test_subject",
                "'AP'",
                "ap.ps_ap_course_subject_code",
                "cast(null as int64)",
            ]
        )
    }} as assessment_key,

    cast(null as date) as test_date_key,

    ap.student_number,
    ap.academic_year,

    'AP' as assessment_scope,

    ap.test_subject as subject_area,
    ap.ps_ap_course_subject_code as score_type,

    cast(ap.exam_score as numeric) as scale_score,

    cast(null as numeric) as percent_correct,
    cast(null as string) as administration_round,
    cast(null as string) as course_discipline,

    'Official' as test_type,

    ap.rn_highest,

    cast(null as numeric) as max_scale_score,
    cast(null as numeric) as superscore,
    cast(null as numeric) as running_max_scale_score,
    cast(null as string) as aligned_subject_area,
    cast(null as string) as aligned_subject,

    case
        when ap.exam_score >= 3 then 'Qualified' else 'Not Qualified'
    end as proficiency_level,

    ap.score_source,
from ap_assessments as ap
