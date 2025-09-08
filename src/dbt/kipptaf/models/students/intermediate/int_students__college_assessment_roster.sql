with
    scores as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.student_number,
            e.studentid,
            e.students_dcid,
            e.salesforce_id,
            e.grade_level,

            a.administration_round,
            a.test_type,
            a.test_date,
            a.test_month,
            a.scope,
            a.subject_area,
            a.course_discipline,
            a.score_type,
            a.scale_score,
            a.previous_total_score_change,
            a.rn_highest,
            a.max_scale_score,
            a.superscore,

            s.admin_season,
            s.admin_season_order,
            s.grade_season,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            {{ ref("int_assessments__college_assessment") }} as a
            on e.academic_year = a.academic_year
            and e.student_number = a.student_number
        left join
            {{ ref("stg_google_sheets__kippfwd_seasons") }} as s
            on a.scope = s.scope
            and a.test_month = s.test_month
            and e.grade_level = s.grade_level
        where e.school_level = 'HS' and e.rn_year = 1
    ),

    -- trunk-ignore(sqlfluff/ST03)
    running_max_score as (
        select
            student_number,
            academic_year,
            scope,
            score_type,
            grade_season,

            max(scale_score) over (
                partition by student_number, score_type order by grade_season
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

    dedup_running_max_score as (
        {{
            dbt_utils.deduplicate(
                relation="running_max_score",
                partition_by="student_number,score_type,grade_season",
                order_by="student_number",
            )
        }}
    ),

    -- trunk-ignore(sqlfluff/ST03)
    running_superscore as (
        select
            student_number,
            scope,
            grade_season,

            round(
                if(
                    scope = 'ACT',
                    avg(running_max_scale_score) over (
                        partition by student_number, grade_season
                    ),
                    sum(running_max_scale_score) over (
                        partition by student_number, grade_season
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
                partition_by="student_number,scope,grade_season",
                order_by="student_number",
            )
        }}
    )

select
    s.*,

    dm.running_max_scale_score,

    coalesce(dr.runnning_superscore, s.superscore) as running_superscore,

from scores as s
left join
    dedup_running_max_score as dm
    on s.student_number = dm.student_number
    and s.grade_season = dm.grade_season
    and s.score_type = dm.score_type
left join
    dedup_runnning_superscore as dr
    on s.student_number = dr.student_number
    and s.scope = dr.scope
    and s.grade_season = dr.grade_season
