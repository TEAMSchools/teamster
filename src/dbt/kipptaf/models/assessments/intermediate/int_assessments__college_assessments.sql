with
    college_assessments as (
        select
            contact,
            test_type as scope,
            date as test_date,
            score as scale_score,

            'Official' as test_type,

            concat(
                format_date('%b', date), ' ', format_date('%g', date)
            ) as administration_round,

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
            safe_cast(local_student_id as string) as contact,

            'PSAT' as scope,

            test_date,
            score as scale_score,

            'Official' as test_type,

            concat(
                format_date('%b', test_date), ' ', format_date('%g', test_date)
            ) as administration_round,

            case
                score_type
                when 'total_score'
                then 'Composite'
                when 'reading_test_score'
                then 'Reading'
                when 'math_test_score'
                then 'Math Test'
                when 'math_section_score'
                then 'Math'
                when 'eb_read_write_section_score'
                then 'Writing and Language Test'
            end as subject_area,
            case
                when score_type in ('eb_read_write_section_score', 'reading_test_score')
                then 'ENG'
                when score_type in ('math_test_score', 'math_section_score')
                then 'MATH'
                else 'NA'
            end as course_discipline,

            academic_year as test_academic_year,
        from {{ ref("int_illuminate__psat_unpivot") }}
        where
            score_type in (
                'eb_read_write_section_score',
                'math_section_score',
                'math_test_score',
                'reading_test_score',
                'total_score'
            )
    )

select *
from college_assessments
where scope = 'PSAT'
