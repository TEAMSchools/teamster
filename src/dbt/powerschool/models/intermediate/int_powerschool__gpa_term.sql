with
    grade_detail as (
        /* current year */
        select
            studentid,
            schoolid,
            yearid,
            storecode,
            term_percent_grade,
            term_grade_points,
            y1_letter_grade,
            y1_percent_grade_adjusted,
            y1_grade_points,
            y1_grade_points_unweighted,
            potential_credit_hours as potential_credit_hours_default,
            termbin_is_current as is_current,

            if(
                term_percent_grade is null, null, potential_credit_hours
            ) as potential_credit_hours_term,

            if(
                y1_percent_grade_adjusted is null, null, potential_credit_hours
            ) as potential_credit_hours_y1,
        from {{ ref("base_powerschool__final_grades") }}
        where exclude_from_gpa = 0 and potential_credit_hours > 0

        union all

        /* previous years */
        select
            y1.studentid,
            y1.schoolid,
            y1.yearid,

            storecode,

            sg.percent as term_percent_grade,
            sg.gpa_points as term_grade_points,

            y1.grade as y1_letter_grade,
            y1.percent as y1_percent_grade_adjusted,
            y1.gpa_points as y1_grade_points,

            null as y1_grade_points_unweighted,

            c.credit_hours as potential_credit_hours_default,

            if(storecode in ('Q4', 'T3'), true, false) as is_current,

            if(sg.percent is null, null, c.credit_hours) as potential_credit_hours_term,

            if(y1.percent is null, null, c.credit_hours) as potential_credit_hours_y1,
        from {{ ref("stg_powerschool__storedgrades") }} as y1
        cross join unnest(["Q1", "Q2", "Q3", "Q4"]) as storecode
        inner join
            {{ ref("stg_powerschool__courses") }} as c
            on y1.course_number = c.course_number
            and c.credit_hours > 0
        left join
            {{ ref("stg_powerschool__storedgrades") }} as sg
            on y1.studentid = sg.studentid
            and y1.yearid = sg.yearid
            and y1.course_number = sg.course_number
            and storecode = sg.storecode
        where
            y1.storecode = 'Y1'
            and y1.excludefromgpa = 0
            and y1.yearid < {{ var("current_academic_year") - 1990 }}
    ),

    grade_rollup as (
        select
            studentid,
            schoolid,
            yearid,
            storecode,
            is_current,

            case
                when storecode in ('Q1', 'Q2')
                then 'S1'
                when storecode in ('Q3', 'Q4')
                then 'S2'
            end as semester,

            sum(potential_credit_hours_term) as total_credit_hours_term,
            sum(potential_credit_hours_y1) as total_credit_hours_y1,

            sum(term_grade_points) as gpa_points_total_term,
            sum(y1_grade_points) as gpa_points_total_y1,

            avg(term_percent_grade) as grade_avg_term,
            avg(y1_percent_grade_adjusted) as grade_avg_y1,

            sum(
                potential_credit_hours_default * term_grade_points
            ) as weighted_gpa_points_term,
            sum(
                potential_credit_hours_default * y1_grade_points
            ) as weighted_gpa_points_y1,
            sum(
                potential_credit_hours_default * y1_grade_points_unweighted
            ) as weighted_gpa_points_y1_unweighted,

            sum(if(y1_letter_grade like 'F%', 1, 0)) as n_failing_y1,
        from grade_detail
        group by studentid, yearid, storecode, is_current, schoolid
    ),

    gpa_calcs as (
        select
            *,

            round(
                safe_divide(weighted_gpa_points_term, total_credit_hours_term), 2
            ) as gpa_term,

            round(
                safe_divide(weighted_gpa_points_y1, total_credit_hours_y1), 2
            ) as gpa_y1,

            round(
                safe_divide(weighted_gpa_points_y1_unweighted, total_credit_hours_y1), 2
            ) as gpa_y1_unweighted,
        from grade_rollup
    )

select
    studentid,
    schoolid,
    yearid,
    storecode as term_name,
    semester,
    is_current,
    gpa_points_total_term,
    gpa_term,
    gpa_points_total_y1,
    gpa_y1,
    gpa_y1_unweighted,
    n_failing_y1,
    total_credit_hours_term,
    total_credit_hours_y1,

    round(grade_avg_term, 0) as grade_avg_term,
    round(grade_avg_y1, 0) as grade_avg_y1,
    round(weighted_gpa_points_term, 2) as weighted_gpa_points_term,
    round(weighted_gpa_points_y1, 2) as weighted_gpa_points_y1,
    round(weighted_gpa_points_y1_unweighted, 2) as weighted_gpa_points_y1_unweighted,

    /* gpa semester */
    sum(gpa_points_total_term) over (
        partition by studentid, yearid, semester
    ) as gpa_points_total_semester,

    round(
        sum(weighted_gpa_points_term) over (partition by studentid, yearid, semester), 2
    ) as weighted_gpa_points_semester,

    round(
        sum(total_credit_hours_y1) over (partition by studentid, yearid, semester), 2
    ) as total_credit_hours_semester,

    round(
        avg(grade_avg_term) over (partition by studentid, yearid, semester), 0
    ) as grade_avg_semester,

    round(
        safe_divide(
            sum(weighted_gpa_points_term) over (
                partition by studentid, yearid, semester
            ),
            sum(total_credit_hours_term) over (partition by studentid, yearid, semester)
        ),
        2
    ) as gpa_semester,
from gpa_calcs
