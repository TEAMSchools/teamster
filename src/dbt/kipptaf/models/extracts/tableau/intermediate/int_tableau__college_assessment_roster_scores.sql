with
    scores as (
        select
            student_number,
            test_type,
            score_type,
            aligned_month_round,
            scale_score,

            -- SAT only; unbinding the rest keeps grade-11 NMSQT. TODO(#4658)
            if(scope = 'SAT', academic_year, null) as bound_academic_year,

        from {{ ref("int_assessments__all_college_assessments") }}
        where test_date is not null
    ),

    expected_scores as (
        select
            e.student_number,
            e.grade_level,

            a.expected_test_type,
            a.expected_scope,
            a.expected_score_type,
            a.expected_grouping,
            a.expected_admin_season,
            a.expected_admin_season_order,
            a.expected_field_name,

            s.scale_score,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            {{ ref("stg_google_sheets__kippfwd__expected_assessments") }} as a
            on e.region = a.expected_region
            and e.grade_level = a.expected_grade_level
        inner join
            scores as s
            on e.student_number = s.student_number
            and a.expected_test_type = s.test_type
            and a.expected_score_type = s.score_type
            and a.expected_month_round = s.aligned_month_round
            and e.academic_year = coalesce(s.bound_academic_year, e.academic_year)
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

        from expected_scores
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

    /* grade_level and expected_test_type are carried for the join back below, not
       for the window. A season name is not unique within a scope -- the tab states
       SAT Winter at both grade 11 and grade 12, and SAT Fall as both grade 11
       Practice and grade 12 Official -- so joining on season alone would attach
       both grades' growth to both grades' rows. The partition deliberately omits
       them, because chaining growth across grades and test types is the point. */
    growth as (
        select
            student_number,
            grade_level,
            expected_test_type,
            expected_scope,
            expected_admin_season,

            -- season order is reverse-chronological, so desc walks forwards in time
            scale_score - lag(scale_score) over (
                partition by student_number, expected_scope
                order by expected_admin_season_order desc
            ) as total_growth_score_change,

        from final_scores
        where expected_grouping = 'Total' and expected_scope = 'SAT'
    ),

    scored as (
        select
            s.student_number,
            s.grade_level,
            s.expected_test_type,
            s.expected_grouping,
            s.expected_scope,
            s.expected_score_type,
            s.expected_admin_season,
            s.expected_admin_season_order,
            s.expected_field_name,
            s.scale_score,

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
            and s.grade_level = g.grade_level
            and s.expected_test_type = g.expected_test_type
            and s.expected_scope = g.expected_scope
            and s.expected_admin_season = g.expected_admin_season
            and g.total_growth_score_change is not null
    )

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
    unique_test_admin_id,
    score,
    score_category,

/* Long on score category, matching expected_score_category on the tab, so a
   reporting view joins straight through instead of unioning the two itself.
   UNPIVOT drops null rows, so an administration with no growth yields no Score
   Change row at all rather than one holding null -- a consumer left joining the
   scaffold reads null either way. */
from
    scored unpivot (
        score for score_category
        in (scale_score as 'Scale Score', total_growth_score_change as 'Score Change')
    )
