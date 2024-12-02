with
    college_assessments as (
        select
            student_number,
            test_type as scope,
            date as test_date,
            score as scale_score,
            score_type,

            'Official' as test_type,

            concat(
                format_date('%b', date), ' ', format_date('%g', date)
            ) as administration_round,

            case
                when
                    score_type in (
                        'act_reading',
                        'act_english',
                        'sat_reading_test_score',
                        'sat_ebrw'
                    )
                then 'ELA'
                when score_type in ('act_math', 'sat_math_test_score', 'sat_math')
                then 'Math'
                when score_type = 'act_science'
                then 'Science'
            end as discipline,

            case
                score_type
                when 'sat_total_score'
                then 'Composite'
                when 'sat_reading_test_score'
                then 'Reading Test'
                when 'sat_math_test_score'
                then 'Math Test'
                else test_subject
            end as subject_area,

            case
                when
                    score_type in (
                        'act_reading',
                        'act_english',
                        'sat_reading_test_score',
                        'sat_ebrw'
                    )
                then 'ENG'
                when score_type in ('act_math', 'sat_math_test_score', 'sat_math')
                then 'MATH'
                else 'NA'
            end as course_discipline,

            {{
                date_to_fiscal_year(
                    date_field="date", start_month=7, year_source="start"
                )
            }} as test_academic_year,
        from {{ ref("int_kippadb__standardized_test_unpivot") }}
        where
            score_type in (
                'act_composite',
                'act_reading',
                'act_math',
                'act_english',
                'act_science',
                'sat_total_score',
                'sat_reading_test_score',
                'sat_math_test_score',
                'sat_math',
                'sat_ebrw'
            )

        union all

        select
            cast(local_student_id as numeric) as student_number,

            'PSAT' as scope,

            test_date,
            score as scale_score,
            score_type,

            'Official' as test_type,

            concat(
                format_date('%b', test_date), ' ', format_date('%g', test_date)
            ) as administration_round,

            case
                when
                    score_type
                    in ('psat_eb_read_write_section_score', 'psat_reading_test_score')
                then 'ELA'
                when score_type in ('psat_math_section_score', 'psat_math_test_score')
                then 'Math'
            end as discipline,

            case
                score_type
                when 'psat_total_score'
                then 'Composite'
                when 'psat_reading_test_score'
                then 'Reading'
                when 'psat_math_test_score'
                then 'Math Test'
                when 'psat_math_section_score'
                then 'Math'
                when 'psat_eb_read_write_section_score'
                then 'Writing and Language Test'
            end as subject_area,
            case
                when
                    score_type
                    in ('psat_eb_read_write_section_score', 'psat_reading_test_score')
                then 'ENG'
                when score_type in ('psat_math_test_score', 'psat_math_section_score')
                then 'MATH'
                else 'NA'
            end as course_discipline,

            academic_year as test_academic_year,
        from {{ ref("int_illuminate__psat_unpivot") }}
        where
            score_type in (
                'psat_eb_read_write_section_score',
                'psat_math_section_score',
                'psat_math_test_score',
                'psat_reading_test_score',
                'psat_total_score'
            )
    )

select
    test_academic_year,
    student_number,
    test_type,
    scope,
    score_type,
    subject_area,
    discipline,
    course_discipline,
    administration_round,
    test_date,
    scale_score,

    -- this rn doesnt account for which version of the psat was taken
    -- dont ever change this to partition on discipline or you will lose the section
    -- vs score rows (XX vs XXX scores)
    row_number() over (
        partition by student_number, scope, subject_area order by scale_score desc
    ) as rn_highest,

from college_assessments
