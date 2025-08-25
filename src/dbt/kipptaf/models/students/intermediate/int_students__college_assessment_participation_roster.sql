with
    base_rows as (
        select
            _dbt_source_relation,
            student_number,
            studentid,
            students_dcid,
            salesforce_id,
            grade_level,
            scope,
            score_type,

        from {{ ref("int_students__college_assessment_roster") }}
        where
            score_type in (
                'act_composite',
                'sat_total_score',
                'psat89_total',
                'psatnmsqt_total',
                'psat10_total'
            )
    ),

    yearly_test_counts as (
        select
            _dbt_source_relation,
            student_number,
            studentid,
            students_dcid,
            salesforce_id,
            grade_level,

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
        group by
            _dbt_source_relation,
            student_number,
            studentid,
            students_dcid,
            salesforce_id,
            grade_level
    )

select
    *,

    sum(psat89_count) over (
        partition by student_number order by grade_level
    ) as psat89_count_ytd,

    sum(psat10_count) over (
        partition by student_number order by grade_level
    ) as psat10_count_ytd,

    sum(psatnmsqt_count) over (
        partition by student_number order by grade_level
    ) as psatnmsqt_count_ytd,

    sum(sat_count) over (
        partition by student_number order by grade_level
    ) as sat_count_ytd,

    sum(act_count) over (
        partition by student_number order by grade_level
    ) as act_count_ytd,

from yearly_test_counts
where student_number = 11737
order by grade_level
