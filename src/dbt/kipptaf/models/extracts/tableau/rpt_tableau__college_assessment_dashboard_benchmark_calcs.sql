with
    scaffold as (
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

            regexp_extract(benchmark_group, r'^(.+)_[^_]+_[^_]+$') as scope,
            regexp_extract(benchmark_group, r'^.+_([^_]+)_[^_]+$') as subject_area,
            regexp_extract(benchmark_group, r'_([^_]+)$') as benchmark_name,

            if(
                regexp_extract(benchmark_group, r'^(.+)_[^_]+_[^_]+$')
                in ('PSAT10', 'PSAT NMSQT'),
                'PSAT10/NMSQT',
                regexp_extract(benchmark_group, r'^(.+)_[^_]+_[^_]+$')
            ) as aligned_scope,

        from {{ ref("int_extracts__student_enrollments") }}
        cross join
            unnest(
                [
                    'PSAT 8/9_EBRW_EBRW',
                    'PSAT NMSQT_EBRW_EBRW',
                    'PSAT10_EBRW_EBRW',
                    'SAT_EBRW_EBRW',
                    'PSAT 8/9_Math_Math',
                    'PSAT NMSQT_Math_Math',
                    'PSAT10_Math_Math',
                    'SAT_Math_Math',
                    'PSAT 8/9_Combined_College-Ready',
                    'PSAT 8/9_Combined_EA/ED-Ready',
                    'PSAT 8/9_Combined_HS-Ready',
                    'PSAT NMSQT_Combined_College-Ready',
                    'PSAT NMSQT_Combined_EA/ED-Ready',
                    'PSAT NMSQT_Combined_HS-Ready',
                    'PSAT10_Combined_College-Ready',
                    'PSAT10_Combined_EA/ED-Ready',
                    'PSAT10_Combined_HS-Ready',
                    'SAT_Combined_College-Ready',
                    'SAT_Combined_EA/ED-Ready',
                    'SAT_Combined_HS-Ready'
                ]
            ) as benchmark_group
        where
            school_level = 'HS'
            and rn_undergrad = 1
            and rn_year = 1
            and grad_iep_exempt_status_overall != 'Yes'
            and graduation_year is not null
            and not is_out_of_district
    ),

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
            e.scope,
            e.aligned_scope,
            e.subject_area,
            e.benchmark_name,

            s.test_type,
            s.score_type,
            s.scale_score,

            max(s.scale_score) over (
                partition by e.student_number, e.aligned_scope, e.subject_area
            ) as max_score,

        from scaffold as e
        left join
            aligned_scores as s
            on e.student_number = s.student_number
            and e.aligned_scope = s.aligned_scope
            and e.subject_area = s.subject_area
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
    scope,
    aligned_scope,
    test_type,
    score_type,
    subject_area,
    max_score,
    benchmark_name,

from base
where scale_score = max_score or max_score is null
