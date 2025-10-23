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

            'Official' as test_type,
            null as salesforce_id,

            format_date('%B', latest_psat_date) as test_month,

            if(average_rows = 1, false, true) as is_multi_row,

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

            'Official' as test_type,
            contact as salesforce_id,

            format_date('%B', `date`) as test_month,

            if(average_rows = 1, false, true) as is_multi_row,

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

    growth as (
        select
            academic_year,
            student_number,
            scope,
            test_date,
            scale_score,

            scale_score - lag(scale_score) over (
                partition by student_number, scope order by test_date
            ) as previous_total_score_change,

        from scores
        where subject_area in ('Composite', 'Combined') and test_date is not null
    ),

    max_score as (
        select
            student_number,
            scope,
            score_type,
            is_multi_row,

            avg(scale_score) as max_scale_score,

        from scores
        where
            score_type not in (
                'psat10_reading',
                'psat10_math_test',
                'sat_math_test_score',
                'sat_reading_test_score'
            )
            and rn_highest = 1
        group by student_number, scope, score_type, is_multi_row
    ),

    max_total_score as (
        select
            student_number,
            scope,

            if(scope = 'ACT', avg(max_scale_score), sum(max_scale_score)) as superscore,

        from max_score
        where
            score_type not in (
                'act_composite',
                'sat_total_score',
                'psat89_total',
                'psat10_total',
                'psatnmsqt_total'
            )
        group by student_number, scope
    ),

    alt_superscore as (
        select student_number, scope, avg(max_scale_score) as superscore,

        from max_score
        where
            score_type in (
                'act_composite',
                'sat_total_score',
                'psat89_total',
                'psat10_total',
                'psatnmsqt_total'
            )
            and not is_multi_row
        group by student_number, scope
    ),

    {# running_max_score as (
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
        where test_date is not null
    ),

    dedup_running_max_score as (
        {{
            dbt_utils.deduplicate(
                relation="running_max_score",
                partition_by="student_number,score_type,test_date",
                order_by="student_number",
            )
        }}
    ),

    running_superscore as (
        select
            student_number,
            scope,
            test_date,

            round(
                if(
                    scope = 'ACT',
                    avg(running_max_scale_score) over (
                        partition by student_number, test_date
                    ),
                    sum(running_max_scale_score) over (
                        partition by student_number, test_date
                    )
                ),
                0
            ) as runnning_superscore,

        from running_max_score
        where
            score_type not in (
                'act_composite',
                'sat_total_score',
                'psat89_total',
                'psat10_total',
                'psatnmsqt_total'
            )
    ),

    dedup_runnning_superscore as (
        {{
            dbt_utils.deduplicate(
                relation="running_superscore",
                partition_by="student_number,scope,test_date",
                order_by="student_number",
            )
        }}
    ), #}
    score_calcs as (
        select
            s.*,

            m.max_scale_score,

            max(s.scale_score) over (
                partition by s.student_number, s.score_type order by s.test_date asc
            ) as running_max_scale_score,

            g.previous_total_score_change,

            if(
                s.subject_area in ('Composite', 'Combined'), 'Total', s.subject_area
            ) as aligned_subject_area,

            round(coalesce(d.superscore, a.superscore), 0) as superscore,

            {# round(
                coalesce(dr.runnning_superscore, a.superscore), 0
            ) as running_superscore, #}
            {{
                dbt_utils.generate_surrogate_key(
                    ["s.student_number", "s.test_type", "s.score_type", "s.test_date"]
                )
            }} as surrogate_key,

        from scores as s
        left join
            max_score as m
            on s.student_number = m.student_number
            and s.score_type = m.score_type
        left join
            max_total_score as d
            on s.student_number = d.student_number
            and s.scope = d.scope
        left join
            alt_superscore as a
            on s.student_number = a.student_number
            and s.scope = a.scope
        left join
            growth as g
            on s.student_number = g.student_number
            and s.scope = g.scope
            and s.test_date = g.test_date
            and g.previous_total_score_change is not null
    ),

    running_max_superscores as (
        select
            *,

            avg(
                if(
                    score_type in (
                        'act_composite',
                        'sat_total_score',
                        'psat89_total',
                        'psat10_total',
                        'psatnmsqt_total',
                        'sat_reading_test_score',
                        'sat_math_test_score',
                        'psat10_reading',
                        'psat10_math_test'
                    ),
                    null,
                    running_max_scale_score
                )
            ) over (partition by student_number, scope, test_date)
            as avg_running_max_superscore,

            sum(
                if(
                    score_type in (
                        'act_composite',
                        'sat_total_score',
                        'psat89_total',
                        'psat10_total',
                        'psatnmsqt_total',
                        'sat_reading_test_score',
                        'sat_math_test_score',
                        'psat10_reading',
                        'psat10_math_test'
                    ),
                    null,
                    running_max_scale_score
                )
            ) over (partition by student_number, scope, test_date)
            as sum_running_max_superscore,

        from score_calcs
    )

select
    *,

    round(
        case
            when scope = 'ACT'
            then avg_running_max_superscore
            when scope = 'SAT'
            then sum_running_max_superscore
        end,
        0
    ) as runnning_superscore,
from running_max_superscores
