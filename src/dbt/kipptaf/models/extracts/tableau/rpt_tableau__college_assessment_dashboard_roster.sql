with
    scores as (
        select
            student_number,
            score_category,
            score,
            subject_area,

            concat(
                'G',
                grade_level,
                ' ',
                test_month,
                ' ',
                scope,
                ' ',
                test_type,
                ' ',
                subject_area
            ) as field_name,

            concat(
                'G',
                grade_level,
                ' ',
                test_month,
                ' ',
                scope,
                ' ',
                test_type,
                ' ',
                subject_area,
                ' ',
                score_category
            ) as expected_field_name,

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

    expected_fields as (
        select distinct
            'key' as fake_join,

            expected_field_name,

            case
                when
                    filter_group in (
                        'SAT Combined Scale Score',
                        'PSAT NMSQT Combined Scale Score',
                        'PSAT10 Combined Scale Score'
                    )
                then concat(filter_group_month, '_1')

                when
                    filter_group in (
                        'SAT Combined Previous Total Score Change',
                        'PSAT NMSQT Combined Previous Total Score Change',
                        'PSAT10 Combined Previous Total Score Change'
                    )
                then concat(filter_group_month, '_2')

                when
                    filter_group in (
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
    ),

    superscores as (
        select
            student_number, sat_combined_superscore, sat_ebrw_highest, sat_math_highest,

        from
            scores pivot (
                avg(score) for filter_group in (
                    'SAT Combined Superscore' as sat_combined_superscore,
                    'SAT EBRW Max Scale Score' as sat_ebrw_highest,
                    'SAT Math Max Scale Score' as sat_math_highest
                )
            )
    ),

    superscores_dedup as (
        select
            student_number,
            avg(sat_combined_superscore) as sat_combined_superscore,
            avg(sat_ebrw_highest) as sat_ebrw_highest,
            avg(sat_math_highest) as sat_math_highest,

        from superscores
        group by student_number
    ),

    focus_scores as (
        select
            student_number,
            field_name,
            expected_field_name,
            subject_area,
            filter_group,
            field_name
            score_category,
            score,

        from scores
        where
            filter_group in (
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
    ),

    students as (
        select
            region,
            schoolid,
            school,
            student_number,
            salesforce_id,
            student_name,
            student_first_name,
            student_last_name,
            grade_level,
            student_email,
            enroll_status,
            ktc_cohort,
            graduation_year,
            year_in_network,
            iep_status,
            grad_iep_exempt_status_overall,
            cumulative_y1_gpa,
            cumulative_y1_gpa_projected,
            college_match_gpa,
            college_match_gpa_bands,

            'key' as fake_join,

        from {{ ref("int_extracts__student_enrollments") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and graduation_year = {{ var("current_academic_year") + 1 }}
            and school_level = 'HS'
            and rn_year = 1
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
    e.graduation_year,
    e.year_in_network,
    e.iep_status,
    e.grad_iep_exempt_status_overall,
    e.cumulative_y1_gpa,
    e.cumulative_y1_gpa_projected,
    e.college_match_gpa,
    e.college_match_gpa_bands,

    ef.expected_field_name,
    ef.field_name_order,

    s.sat_combined_superscore,
    s.sat_ebrw_highest,
    s.sat_math_highest,

    f.field_name,
    f.subject_area,
    f.filter_group,
    f.score_category,
    f.score,

from students as e
inner join expected_fields as ef on e.fake_join = ef.fake_join
left join superscores_dedup as s on e.student_number = s.student_number
left join
    focus_scores as f
    on e.student_number = f.student_number
    and ef.expected_field_name = f.expected_field_name
