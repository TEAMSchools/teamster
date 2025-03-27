select
    powerschool_student_number as student_number,
    administration_round,
    academic_year,
    latest_psat_date as test_date,
    test_type as scope,
    test_subject as subject_area,
    course_discipline,
    score_type,
    score as scale_score,
    rn_highest,

    'Official' as test_type,
    null as salesforce_id,
    format_date('%B', latest_psat_date) as test_month,

from {{ ref("int_collegeboard__psat_unpivot") }}

union all

select
    null as student_number,

    administration_round,
    academic_year,
    `date` as test_date,
    test_type as scope,
    subject_area,
    course_discipline,
    score_type,
    score as scale_score,
    rn_highest,

    'Official' as test_type,
    contact as salesforce_id,
    format_date('%B', `date`) as test_month,

from {{ ref("int_kippadb__standardized_test_unpivot") }}
where
    `date` is not null
    and test_type in ('ACT', 'SAT')
    and score_type in (
        'act_composite',
        'act_reading',
        'act_english',
        'act_math',
        'act_science',
        'sat_total_score',
        'sat_reading_test_score',
        'sat_math_test_score',
        'sat_math',
        'sat_ebrw'
    )
