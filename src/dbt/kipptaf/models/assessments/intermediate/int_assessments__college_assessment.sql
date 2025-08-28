with
    scores as (
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

            format_date('%B', latest_psat_date) as test_month,
            'Official' as test_type,
            null as salesforce_id,

        from {{ ref("int_collegeboard__psat_unpivot") }}

        union all

        select
            school_specific_id as student_number,
            administration_round,
            academic_year,
            `date` as test_date,
            test_type as scope,
            subject_area,
            course_discipline,
            score_type,
            score as scale_score,
            rn_highest,

            format_date('%B', `date`) as test_month,
            'Official' as test_type,
            contact as salesforce_id,

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
    ),

    max_score as (
        select student_number, scope, score_type, avg(scale_score) as max_scale_score,

        from scores
        where
            score_type not in (
                'psat10_reading',
                'psat10_math_test',
                'sat_math_test_score',
                'sat_reading_test_score'
            )
            and rn_highest = 1
        group by student_number, scope, score_type
    ),

    running_max_score as (
        select
            student_number,
            academic_year,
            scope,
            score_type,
            test_date,

            max(scale_score) over (
                partition by student_number, score_type order by test_date
            ) as running_max_scale_score,

        from scores
        where
            score_type not in (
                'psat10_reading',
                'psat10_math_test',
                'sat_math_test_score',
                'sat_reading_test_score'
            )
    ),

    -- trunk-ignore(sqlfluff/ST03)
    max_total_score as (
        select
            student_number,
            scope,

            if(
                scope = 'ACT',
                avg(max_scale_score) over (partition by student_number, scope),
                sum(max_scale_score) over (partition by student_number, scope)
            ) as superscore,

        from running_max_score
        where score_type not in ('act_composite', 'sat_total_score')
    ),

    dedup_superscore as (
        {{
            dbt_utils.deduplicate(
                relation="max_total_score",
                partition_by="student_number,scope",
                order_by="student_number",
            )
        }}
    ),

    -- trunk-ignore(sqlfluff/ST03)
    running_superscore as (
        select
            student_number,
            scope,

            if(
                scope = 'ACT',
                avg(max_scale_score) over (partition by student_number, scope),
                sum(max_scale_score) over (partition by student_number, scope)
            ) as running_superscore,

        from max_score
        where score_type not in ('act_composite', 'sat_total_score')
    ),

    dedup_runnning_superscore as (
        {{
            dbt_utils.deduplicate(
                relation="running_superscore",
                partition_by="student_number,scope",
                order_by="student_number",
            )
        }}
    ),

    alt_superscore as (
        select student_number, scope, avg(max_scale_score) as superscore,

        from max_score
        where score_type in ('act_composite', 'sat_total_score')
        group by student_number, scope
    )

select
    s.*,

    m.max_scale_score,
    mr.max_running_scale_score,

    round(coalesce(d.superscore, a.superscore)) as superscore,
    round(dr.running_superscore, 1) as running_superscore,

from scores as s
left join
    max_score as m
    on s.student_number = m.student_number
    and s.score_type = m.score_type
left join
    dedup_superscore as d on s.student_number = d.student_number and s.scope = d.scope
left join
    alt_superscore as a on s.student_number = a.student_number and s.scope = a.scope
left join
    max_running_scale_score as mr
    on s.student_number = mr.student_number
    and s.score_type = mr.score_type
left join
    dedup_running_superscore as dr
    on s.student_number = dr.student_number
    and s.scope = dr.scope
