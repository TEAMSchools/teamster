with
    base_rows as (
        select
            e._dbt_source_relation,
            e.student_number,
            e.studentid,
            e.students_dcid,
            e.salesforce_id,
            e.grade_level,

            expected_test,

            a.scope,
            a.score_type,

            concat(e.grade_level, expected_test) as filter_list,

        from {{ ref("int_extracts__student_enrollments") }} as e
        cross join
            unnest(['ACT', 'SAT', 'PSAT 8/9', 'PSAT10', 'PSAT NMSQT']) as expected_test
        left join
            {{ ref("int_assessments__college_assessment") }} as a
            on e.academic_year = a.academic_year
            and e.student_number = a.student_number
            and expected_test = a.scope
            and a.score_type in (
                'act_composite',
                'sat_total_score',
                'psat89_total',
                'psatnmsqt_total',
                'psat10_total'
            )
        where e.school_level = 'HS' and e.rn_year = 1
    )

select
    _dbt_source_relation,
    student_number,
    studentid,
    students_dcid,
    salesforce_id,
    grade_level,

    '' as count_type,

    sum(psat89_count) as psat89_count,
    sum(psat10_count) as psat10_count,
    sum(psatnmsqt_count) as psatnmsqt_count,
    sum(sat_count) as sat_count,
    sum(act_count) as act_count,

from
    base_rows pivot (
        count(score_type) for scope in (
            'PSAT 8/9' as psat89_count,
            'PSAT10' as psat10_count,
            'PSAT NMSQT' as psatnmsqt_count,
            'SAT' as sat_count,
            'ACT' as act_count
        )
    )
where
    filter_list not in (
        '9ACT',
        '9SAT',
        '10PSAT 8/9',
        '11PSAT 8/9',
        '12PSAT 8/9',
        '12PSAT NMSQT',
        '12 PSAT10'
    )
group by
    _dbt_source_relation,
    student_number,
    studentid,
    students_dcid,
    salesforce_id,
    grade_level
