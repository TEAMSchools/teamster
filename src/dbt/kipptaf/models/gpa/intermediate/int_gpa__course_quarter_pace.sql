with
    term_rows as (
        select
            studentid,
            course_number,
            course_name,
            _dbt_source_project,
            potential_credit_hours,
            courses_gradescaleid_unweighted,
            termbin_end_date,
            termbin_is_current,
            term_weighted_points_possible,
            term_percent_grade_adjusted,
            y1_percent_grade_adjusted,
            y1_grade_points_unweighted,

            termbin_end_date < current_date('{{ var("local_timezone") }}') as is_ended,
            termbin_start_date
            <= current_date('{{ var("local_timezone") }}') as is_started,
        from {{ ref("base_powerschool__final_grades") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and exclude_from_gpa = 0
            and not is_dropped_section
            and potential_credit_hours > 0
    ),

    term_rows_ranked as (
        select
            studentid,
            course_number,
            _dbt_source_project,
            termbin_is_current,
            term_percent_grade_adjusted,
            y1_percent_grade_adjusted,
            y1_grade_points_unweighted,

            row_number() over (
                partition by studentid, course_number, _dbt_source_project
                order by termbin_is_current desc, is_started desc, termbin_end_date desc
            ) as rn_current,
        from term_rows
    ),

    courses as (
        select
            studentid,
            course_number,
            _dbt_source_project,

            max(course_name) as course_name,
            max(potential_credit_hours) as potential_credit_hours,
            max(courses_gradescaleid_unweighted) as courses_gradescaleid_unweighted,
            sum(term_weighted_points_possible) as total_weight,
            sum(
                if(
                    is_ended,
                    term_percent_grade_adjusted * term_weighted_points_possible,
                    0.0
                )
            ) as points_banked,
            sum(if(is_ended, 0.0, term_weighted_points_possible)) as remaining_weight,
            logical_and(is_ended) as is_locked,
        from term_rows
        group by studentid, course_number, _dbt_source_project
    ),

    current_values as (
        select
            studentid,
            course_number,
            _dbt_source_project,
            y1_percent_grade_adjusted as y1_percent_current,
            y1_grade_points_unweighted as y1_grade_points_unweighted_current,

            if(
                termbin_is_current, term_percent_grade_adjusted, null
            ) as term_percent_current,
        from term_rows_ranked
        where rn_current = 1
    ),

    paced as (
        select
            c.studentid,
            c.course_number,
            c.course_name,
            c._dbt_source_project,
            c.potential_credit_hours,
            c.courses_gradescaleid_unweighted,
            c.total_weight,
            c.points_banked,
            c.remaining_weight,
            c.is_locked,

            cv.y1_percent_current,
            cv.y1_grade_points_unweighted_current,
            cv.term_percent_current,

            t.schoolid,
            t.target_cutoff_percent,

            round(
                safe_divide(
                    t.target_cutoff_percent * c.total_weight - c.points_banked,
                    c.remaining_weight
                ),
                2
            ) as pace_percent,
        from courses as c
        inner join
            current_values as cv
            on c.studentid = cv.studentid
            and c.course_number = cv.course_number
            and c._dbt_source_project = cv._dbt_source_project
        inner join
            {{ ref("int_gpa__student_quarter_target") }} as t
            on c.studentid = t.studentid
            and c._dbt_source_project = t._dbt_source_project
    )

select
    studentid,
    schoolid,
    course_number,
    course_name,
    _dbt_source_project,
    potential_credit_hours,
    courses_gradescaleid_unweighted,
    target_cutoff_percent,
    y1_percent_current,
    y1_grade_points_unweighted_current,
    term_percent_current,
    total_weight,
    points_banked,
    remaining_weight,
    is_locked,

    if(is_locked, null, pace_percent) as pace_percent,

    coalesce(y1_percent_current < target_cutoff_percent, false) as is_below_target,
    coalesce(not is_locked and pace_percent <= 50, false) as is_secured,
from paced
