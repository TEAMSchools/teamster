with
    -- trunk-ignore(sqlfluff/ST03)
    aligned_scores_pre as (
        select
            student_number,
            test_type,
            score_type,
            subject_area,
            scale_score,

            if(
                scope in ('PSAT10', 'PSAT NMSQT'), 'PSAT10/NMSQT', scope
            ) as aligned_scope,

        from {{ ref("int_assessments__college_assessment") }}
        where
            rn_highest = 1
            and scope != 'ACT'
            and score_type not in (
                'psat10_math_test',
                'psat10_reading',
                'sat_math_test_score',
                'sat_reading_test_score'
            )

        union all

        select
            student_number,
            test_type,
            score_type,
            subject_area,
            scale_score,

            if(
                scope in ('PSAT10', 'PSAT NMSQT'), 'PSAT10/NMSQT', scope
            ) as aligned_scope,

        from {{ ref("int_assessments__college_assessment_practice") }}
        where
            rn_highest = 1
            and scope != 'ACT'
            and score_type not in (
                'psat10_math_test',
                'psat10_reading',
                'sat_math_test_score',
                'sat_reading_test_score'
            )
    ),

    aligned_scores as (
        {{
            dbt_utils.deduplicate(
                relation="aligned_scores_pre",
                partition_by="student_number, aligned_scope, subject_area",
                order_by="scale_score desc",
            )
        }}
    ),

    scaffold as (
        select distinct
            expected_test_type,
            expected_aligned_scope,
            expected_subject_area,

            expected_benchmark_goal,

            if(
                benchmark_min_score = 'hs_ready_min_score', 'HS-Ready', 'College-Ready'
            ) as expecrted_benchmark_name,

        from
            {{ ref("stg_google_sheets__kippfwd__scaffold") }} unpivot (
                expected_benchmark_goal for expected_benchmark_min_score
                in (hs_ready_min_score, college_ready_min_score)
            )
        where
            expected_scope != 'ACT'
            and academic_year = {{ var("current_academic_year") }}
    ),

    base as (
        select
            e.region,
            e.school,
            e.student_number,
            e.student_name,
            e.iep_status,
            e.is_504,
            e.lep_status,
            e.graduation_year,
            e.year_in_network,
            e.college_match_gpa,
            e.college_match_gpa_bands,

            s.expected_test_type,
            s.expected_aligned_scope,
            s.expected_subject_area,
            s.expected_benchmark_name,
            s.expected_benchmark_goal,

            a.test_type,
            a.score_type,
            a.scale_score,

            cast(
                max(a.scale_score) over (
                    partition by
                        e.student_number,
                        s.expected_aligned_scope,
                        s.expected_subject_area
                ) as int64
            ) as max_score,

        from {{ ref("int_extracts__student_enrollments") }} as e
        cross join scaffold as s
        left join
            aligned_scores as a
            on e.student_number = a.student_number
            and s.expected_test_type = a.expected_test_type
            and s.expected_aligned_scope = a.aligned_scope
            and s.expected_subject_area = a.subject_area
        where
            e.school_level = 'HS'
            and e.rn_undergrad = 1
            and e.rn_year = 1
            and e.grad_iep_exempt_status_overall != 'Yes'
            and e.graduation_year is not null
            and not e.is_out_of_district
    )

select
    region,
    school,
    student_number,
    student_name,
    iep_status,
    is_504,
    lep_status,
    graduation_year,
    year_in_network,
    college_match_gpa,
    college_match_gpa_bands,
    aligned_scope,
    test_type,
    score_type,
    subject_area,
    max_score,
    benchmark_name,
    benchmark_goal,

    case
        when max_score is null
        then 'No Data'
        when max_score >= benchmark_goal
        then 'Met'
        else 'Not Met'
    end as met_benchmark_goal,

from base
