with
    expected_tests as (
        select
            e.academic_year,
            e.region,
            e.grade,
            e.admin_season,
            e.`round`,

            count(*) over (
                partition by
                    e.academic_year, e.region, e.grade, e.admin_season, e.`round`
            ) as expected_row_count,

        from {{ ref("stg_google_sheets__dibels_expected_assessments") }} as e
        inner join
            {{ ref("stg_reporting__terms") }} as t
            on e.academic_year = t.academic_year
            and e.region = t.region
            and e.admin_season = t.name
            and e.test_code = t.code
            and t.type = 'LIT'
        where e.assessment_include is null
    )

select
    e.academic_year,
    e.region,
    e.grade,
    e.admin_season,
    e.`round`,
    e.expected_row_count,

    a.student_number,
    a.actual_row_count,

    if(e.expected_row_count = a.actual_row_count, true, false) as completed_test_round,

    if(e.expected_row_count = a.actual_row_count, 1, 0) as completed_test_round_int,

from expected_tests as e
left join
    {{ ref("int_amplify__all_assessments") }} as a
    on e.academic_year = a.academic_year
    and e.region = a.region
    and e.grade = a.assessment_grade_int
    and e.admin_season = a.period
    and e.`round` = a.`round`
