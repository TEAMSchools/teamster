with
    student_ids as (
        select student_number, salesforce_id,
        from {{ ref("int_extracts__student_enrollments") }}
        where rn_undergrad = 1
    )

select
    u.powerschool_student_number as student_number,
    u.administration_round,
    u.academic_year,
    u.latest_psat_date as test_date,
    u.test_type as scope,
    u.test_subject as subject_area,
    u.course_discipline,
    u.score_type,
    u.score as scale_score,
    u.rn_highest,

    format_date('%B', u.latest_psat_date) as test_month,

    'Official' as test_type,
    i.salesforce_id,

from {{ ref("int_collegeboard__psat_unpivot") }} as u
inner join student_ids as i on u.powerschool_student_number = i.student_number

union all

select
    i.student_number,

    u.administration_round,
    u.academic_year,
    u.`date` as test_date,
    u.test_type as scope,
    u.subject_area,
    u.course_discipline,
    u.score_type,
    u.score as scale_score,
    u.rn_highest,

    format_date('%B', u.`date`) as test_month,

    'Official' as test_type,
    u.contact as salesforce_id,

from {{ ref("int_kippadb__standardized_test_unpivot") }} as u
inner join student_ids as i on u.contact = i.salesforce_id
where
    u.`date` is not null
    and u.test_type in ('ACT', 'SAT')
    and u.score_type in (
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
