with
    scaffold as (
        select distinct
            expected_test_type,
            expected_subject_area,
            expected_benchmark_goal,

            if(
                expected_aligned_scope = 'ACT/SAT', 'SAT', expected_aligned_scope
            ) as expected_aligned_scope,

            if(
                expected_benchmark_min_score = 'hs_ready_min_score',
                'HS-Ready',
                'College-Ready'
            ) as expected_benchmark_name,

        from
            {{ ref("stg_google_sheets__kippfwd__scaffold") }} unpivot (
                expected_benchmark_goal for expected_benchmark_min_score
                in (hs_ready_min_score, college_ready_min_score)
            )
        where
            expected_scope != 'ACT'
            and expected_score_type != 'sat_total_score_growth'
            and academic_year = {{ var("current_academic_year") }}
    ),

    benchmark_scores as (
        select
            student_number,
            test_type,
            benchmark_aligned_scope,
            subject_area,

            cast(
                max(max_benchmark_aligned_scale_score_within_test_type) as int64
            ) as max_scale_score,

        from {{ ref("int_assessments__all_college_assessments") }}
        group by student_number, test_type, benchmark_aligned_scope, subject_area
    )

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

    s.expected_test_type as test_type,
    s.expected_aligned_scope as aligned_scope,
    s.expected_subject_area as subject_area,
    s.expected_benchmark_name as benchmark_name,
    s.expected_benchmark_goal as benchmark_goal,

    a.max_scale_score as max_score,

    case
        when a.max_scale_score is null
        then 'No Data'
        when a.max_scale_score >= s.expected_benchmark_goal
        then 'Met'
        else 'Not Met'
    end as met_benchmark_goal,

from {{ ref("int_extracts__student_enrollments") }} as e
cross join scaffold as s
left join
    benchmark_scores as a
    on e.student_number = a.student_number
    and s.expected_test_type = a.test_type
    and s.expected_aligned_scope = a.benchmark_aligned_scope
    and s.expected_subject_area = a.subject_area
where
    e.school_level = 'HS'
    and e.rn_undergrad = 1
    and e.rn_year = 1
    and e.grad_iep_exempt_status_overall != 'Yes'
    and e.graduation_year is not null
    and not e.is_out_of_district
