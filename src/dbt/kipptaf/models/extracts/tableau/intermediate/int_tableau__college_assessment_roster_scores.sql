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

        from {{ ref("int_collegeboard__psat_unpivot") }}
        where score_type not in ('psat10_reading', 'psat10_math_test')

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

        from {{ ref("int_kippadb__standardized_test_unpivot") }}
        where
            `date` is not null
            and score_type in ('sat_total_score', 'sat_math', 'sat_ebrw')
    ),

    focus_scores as (
        -- SAT, as they are month-bound (12th grade only 12th grade)
        select
            e.student_number,
            e.grade_level,

            a.expected_test_type,
            a.expected_scope,
            a.expected_score_type,
            a.expected_admin_season,
            a.expected_admin_season_order,
            a.expected_month,
            a.expected_grouping,
            a.expected_field_name,

            s.test_type,
            s.scope,
            s.score_type,
            s.test_date,
            s.test_month,
            s.scale_score,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            {{ ref("stg_google_sheets__kippfwd_expected_assessments") }} as a
            on e.region = a.expected_region
            and e.grade_level = a.expected_grade_level
            and a.expected_scope = 'SAT'
        inner join
            scores as s
            on a.expected_score_type = s.score_type
            and a.expected_month = s.test_month
            and a.expected_region = e.region
            and a.expected_grade_level = e.grade_level
            and e.student_number = s.student_number
            and e.academic_year = s.academic_year
        where
            e.school_level = 'HS'
            and e.rn_year = 1
            and e.graduation_year >= {{ var("current_academic_year") + 1 }}

        union all

        -- PSAT et all, not month-bound
        select
            e.student_number,
            e.grade_level,

            a.expected_test_type,
            a.expected_scope,
            a.expected_score_type,
            a.expected_admin_season,
            a.expected_admin_season_order,
            a.expected_month,
            a.expected_grouping,
            a.expected_field_name,

            s.test_type,
            s.scope,
            s.score_type,
            s.test_date,
            s.test_month,
            s.scale_score,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            {{ ref("stg_google_sheets__kippfwd_expected_assessments") }} as a
            on e.region = a.expected_region
            and e.grade_level = a.expected_grade_level
            and a.expected_scope != 'SAT'
        inner join
            scores as s
            on a.expected_score_type = s.score_type
            and a.expected_region = e.region
            and a.expected_grade_level = e.grade_level
            and e.student_number = s.student_number
        where
            e.school_level = 'HS'
            and e.rn_year = 1
            and e.graduation_year >= {{ var("current_academic_year") + 1 }}
    ),

    final_scores as (
        select
            student_number,
            grade_level,
            expected_test_type,
            expected_grouping,
            expected_scope,
            expected_score_type,
            expected_admin_season,
            expected_admin_season_order,
            expected_field_name,

            max(scale_score) as scale_score,

        from focus_scores
        group by
            student_number,
            grade_level,
            expected_test_type,
            expected_grouping,
            expected_scope,
            expected_score_type,
            expected_admin_season,
            expected_admin_season_order,
            expected_field_name
    ),

    growth as (
        select
            student_number,
            grade_level,

            expected_scope,
            expected_admin_season,
            expected_admin_season_order,
            scale_score,

            scale_score - lag(scale_score) over (
                partition by student_number, grade_level, expected_scope
                order by expected_admin_season_order desc
            ) as total_growth_score_change_gl,

            scale_score - lag(scale_score) over (
                partition by student_number, expected_scope
                order by expected_admin_season_order desc
            ) as total_growth_score_change,

        from final_scores
        where expected_grouping = 'Total' and expected_scope = 'SAT'
    ),

    max_score as (
        select student_number, scope, score_type, avg(scale_score) as max_scale_score,

        from scores
        where rn_highest = 1
        group by student_number, scope, score_type
    ),

    max_total_score as (
        select student_number, scope, sum(max_scale_score) as superscore,

        from max_score
        where
            score_type not in (
                'sat_total_score', 'psat89_total', 'psat10_total', 'psatnmsqt_total'
            )
        group by student_number, scope
    ),

    alt_superscore as (
        select student_number, scope, avg(max_scale_score) as superscore,

        from max_score
        where
            score_type
            in ('sat_total_score', 'psat89_total', 'psat10_total', 'psatnmsqt_total')
        group by student_number, scope
    )

select
    s.*,

    m.max_scale_score,

    g.total_growth_score_change,

    h.total_growth_score_change_gl,

    round(coalesce(d.superscore, a.superscore), 0) as superscore,

from final_scores as s
left join
    max_score as m
    on s.student_number = m.student_number
    and s.expected_score_type = m.score_type
left join
    max_total_score as d
    on s.student_number = d.student_number
    and s.expected_scope = d.scope
left join
    alt_superscore as a
    on s.student_number = a.student_number
    and s.expected_scope = a.scope
left join
    growth as g
    on s.student_number = g.student_number
    and s.expected_scope = g.expected_scope
    and s.expected_admin_season = g.expected_admin_season
    and g.total_growth_score_change is not null
left join
    growth as h
    on s.student_number = h.student_number
    and s.expected_scope = h.expected_scope
    and s.grade_level = h.grade_level
    and s.expected_admin_season = h.expected_admin_season
    and h.total_growth_score_change_gl is not null
