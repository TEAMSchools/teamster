with
    scores as (
        select
            student_number,
            score_category,
            score,

            concat(scope, ' ', subject_area, ' ', score_category) as filter_group,

            lower(
                concat(
                    'g',
                    grade_level,
                    '_',
                    month_order,
                    '_',
                    test_type,
                    '_',
                    scope_order,
                    '_',
                    subject_area_order
                )
            ) as filter_group_month,

        from
            {{ ref("int_students__college_assessment_roster") }} unpivot (
                score for score_category in (
                    scale_score as 'Scale Score',
                    max_scale_score as 'Max Scale Score',
                    superscore as 'Superscore',
                    previous_total_score_change as 'Previous Total Score Change'
                )
            )
        where
            graduation_year = {{ var("current_academic_year") + 1 }} and scope != 'ACT'
    ),

    focus_scores as (
        select
            student_number,
            filter_group,
            score_category,
            score,

            case
                when
                    filter_group in (
                        'SAT Combined Superscore',
                        'SAT Combined Scale Score',
                        'PSAT NMSQT Combined Scale Score',
                        'PSAT10 Combined Scale Score'
                    )
                then concat(filter_group_month, '_1')

                when
                    filter_group in (
                        'SAT EBRW Max Scale Score',
                        'SAT Combined Previous Total Score Change',
                        'PSAT NMSQT Combined Previous Total Score Change',
                        'PSAT10 Combined Previous Total Score Change'
                    )
                then concat(filter_group_month, '_2')

                when
                    filter_group in (
                        'SAT Math Max Scale Score',
                        'SAT EBRW Scale Score',
                        'PSAT NMSQT EBRW Scale Score',
                        'PSAT10 EBRW Scale Score'
                    )
                then concat(filter_group_month, '_3')

                when
                    filter_group in (
                        'SAT Math Scale Score',
                        'PSAT NMSQT Math Scale Score',
                        'PSAT10 Math Scale Score'
                    )
                then concat(filter_group_month, '_4')
            end as field_name_order,

        from scores
        where
            filter_group in (
                'SAT Combined Superscore',
                'SAT EBRW Max Scale Score',
                'SAT Math Max Scale Score',
                'SAT Combined Scale Score',
                'SAT Combined Previous Total Score Change',
                'SAT EBRW Scale Score',
                'SAT Math Scale Score',
                'PSAT NMSQT Combined Scale Score',
                'PSAT NMSQT Combined Previous Total Score Change',
                'PSAT NMSQT EBRW Scale Score',
                'PSAT NMSQT Math Scale Score',
                'PSAT10 Combined Scale Score',
                'PSAT10 Combined Previous Total Score Change',
                'PSAT10 EBRW Scale Score',
                'PSAT10 Math Scale Score'
            )
    )

select
    e.region,
    e.schoolid,
    e.school,
    e.student_number,
    e.salesforce_id,
    e.student_name,
    e.student_first_name,
    e.student_last_name,
    e.grade_level,
    e.student_email,
    e.enroll_status,
    e.ktc_cohort,
    e.year_in_network,
    e.iep_status,
    e.grad_iep_exempt_status_overall,
    e.cumulative_y1_gpa,
    e.cumulative_y1_gpa_projected,
    e.college_match_gpa,
    e.college_match_gpa_bands,

    f.filter_group,
    f.score_category,
    f.field_name_order,
    f.score,

from {{ ref("int_extracts__student_enrollments") }} as e
left join focus_scores as f on e.student_number = f.student_number
where
    e.academic_year = {{ var("current_academic_year") }}
    and e.graduation_year = {{ var("current_academic_year") + 1 }}
    and e.school_level = 'HS'
    and e.rn_year = 1
