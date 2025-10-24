with
    score_union as (
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
            contact as salesforce_id,

            count(*) over (
                partition by school_specific_id, test_type, `date`
            ) as row_count_by_test_date,

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

        union all

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

            cast(null as string) as salesforce_id,

            count(*) over (
                partition by powerschool_student_number, test_type, latest_psat_date
            ) as row_count_by_test_date,

        from {{ ref("int_collegeboard__psat_unpivot") }}
    ),

    scores as (
        select
            *,

            if(
                subject_area in ('Composite', 'Combined'), 'Total', subject_area
            ) as aligned_subject_area,

            mod(
                cast(
                    avg(row_count_by_test_date) over (
                        partition by student_number, scope
                    ) as numeric
                ),
                1
            )
            != 0 as is_multirow,

            max(scale_score) over (
                partition by student_number, score_type order by test_date asc
            ) as running_max_scale_score,

            {{
                dbt_utils.generate_surrogate_key(
                    ["student_number", "score_type", "test_date"]
                )
            }} as surrogate_key,

        from score_union
    ),

    growth as (
        select
            academic_year,
            student_number,
            scope,
            test_date,
            scale_score,

            scale_score - lag(scale_score) over (
                partition by student_number, scope order by test_date asc
            ) as previous_total_score_change,

        from scores
        where subject_area in ('Composite', 'Combined') and test_date is not null
    ),

    max_score as (
        select
            student_number,
            scope,
            score_type,
            is_multirow,

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
        group by student_number, scope, score_type, is_multirow
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
            and not is_multirow
        group by student_number, scope
    ),

    score_calcs as (
        select
            s.*,

            m.max_scale_score,

            g.previous_total_score_change,

            round(coalesce(d.superscore, a.superscore), 0) as superscore,

            avg(
                if(
                    s.score_type in (
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
                    s.running_max_scale_score
                )
            ) over (partition by s.student_number, s.scope, s.test_date)
            as avg_running_max_superscore,

            sum(
                if(
                    s.score_type in (
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
                    s.running_max_scale_score
                )
            ) over (partition by s.student_number, s.scope, s.test_date)
            as sum_running_max_superscore,
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
    )

select
    *,

    'Official' as test_type,

    format_date('%B', test_date) as test_month,

    round(
        case
            when scope = 'ACT'
            then avg_running_max_superscore
            when scope = 'SAT'
            then sum_running_max_superscore
        end,
        0
    ) as runnning_superscore,

from score_calcs
