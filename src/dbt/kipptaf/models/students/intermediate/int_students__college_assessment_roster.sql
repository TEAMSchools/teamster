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
            a.rn_highest,
            a.max_scale_score,
            a.superscore,

            s.admin_season,

            case
                s.admin_season when 'BOY' then 1 when 'MOY' then 2 else 3
            end as admin_season_order,

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

    running_max_score as (
        select
            student_number,
            academic_year,
            scope,
            score_type,
            scale_score,
            admin_season,
            admin_season_order,

            max(scale_score) over (
                partition by student_number, score_type
                order by academic_year, admin_season_order
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

    running_superscore as (
        select
            student_number,
            scope,
            admin_season,

            if(
                scope = 'ACT',
                avg(running_max_scale_score) over (partition by student_number, scope),
                sum(running_max_scale_score) over (partition by student_number, scope)
            ) as superscore,

        from running_max_score
        where score_type not in ('act_composite', 'sat_total_score')
    )

select *
from running_superscore
