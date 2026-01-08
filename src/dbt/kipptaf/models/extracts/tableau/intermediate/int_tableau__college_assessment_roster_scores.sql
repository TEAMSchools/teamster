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

            format_date('%B', latest_psat_date) as test_month,

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

            'Official' as test_type,

            format_date('%B', `date`) as test_month,

        from {{ ref("int_kippadb__standardized_test_unpivot") }}
        where
            `date` is not null
            and score_type in ('sat_total_score', 'sat_math', 'sat_ebrw')
    ),

    focus_scores as (
        -- SAT (year/month-bound)
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
            {{ ref("stg_google_sheets__kippfwd__expected_assessments") }} as a
            on e.region = a.expected_region
            and e.grade_level = a.expected_grade_level
            and a.expected_scope = 'SAT'
        inner join
            scores as s
            on e.student_number = s.student_number
            and e.academic_year = s.academic_year
            and a.expected_score_type = s.score_type
            and a.expected_month = s.test_month
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
            {{ ref("stg_google_sheets__kippfwd__expected_assessments") }} as a
            on e.region = a.expected_region
            and e.grade_level = a.expected_grade_level
            and a.expected_scope != 'SAT'
        inner join
            scores as s
            on e.student_number = s.student_number
            and a.expected_score_type = s.score_type
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
                partition by student_number, expected_scope
                order by expected_admin_season_order desc
            ) as total_growth_score_change,

        from final_scores
        where expected_grouping = 'Total' and expected_scope = 'SAT'
    )

select
    s.*,

    g.total_growth_score_change,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "s.expected_test_type",
                "s.expected_score_type",
                "s.grade_level",
                "s.expected_admin_season",
            ]
        )
    }} as unique_test_admin_id,

from final_scores as s
left join
    growth as g
    on s.student_number = g.student_number
    and s.expected_scope = g.expected_scope
    and s.expected_admin_season = g.expected_admin_season
    and g.total_growth_score_change is not null
