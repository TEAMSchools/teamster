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
            if(
                term_percent_grade is null, null, potential_credit_hours
            ) as potential_credit_hours_term,
            if(
                y1_percent_grade_adjusted is null, null, potential_credit_hours
            ) as potential_credit_hours_y1,
            if(
                current_date('{{ var("local_timezone") }}')
                between termbin_start_date and termbin_end_date,
                true,
                false
            ) as is_current,
        from {{ ref("base_powerschool__final_grades") }}
        where exclude_from_gpa = 0 and potential_credit_hours > 0

        union all

        /* previous years */
        select
            sg.studentid,
            sg.schoolid,
            sg.yearid,
            sg.storecode,
            sg.percent as term_percent_grade,
            sg.gpa_points as term_grade_points,

            y1.grade as y1_letter_grade,
            y1.percent as y1_percent_grade_adjusted,
            y1.gpa_points as y1_grade_points,

            null as y1_grade_points_unweighted,

            c.credit_hours as potential_credit_hours_default,
            if(sg.percent is null, null, c.credit_hours) as potential_credit_hours_term,
            if(y1.percent is null, null, c.credit_hours) as potential_credit_hours_y1,

            if(sg.storecode in ('Q4', 'T3'), true, false) as is_current,
        from {{ ref("stg_powerschool__storedgrades") }} as sg
        inner join
            {{ ref("stg_powerschool__courses") }} as c
            on sg.course_number = c.course_number
            and c.credit_hours > 0
        left join
            {{ ref("stg_powerschool__storedgrades") }} as y1
            on sg.studentid = y1.studentid
            and sg.yearid = y1.yearid
            and sg.course_number = y1.course_number
            and y1.storecode = 'Y1'
        where
            sg.storecode_type in ('Q', 'T')
            and sg.excludefromgpa = 0
            and sg.yearid < {{ var("current_academic_year") }}
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

            /* gpa term */
            round(avg(term_percent_grade), 0) as grade_avg_term,
            sum(term_grade_points) as gpa_points_total_term,
            sum(
                potential_credit_hours_default * term_grade_points
            ) as weighted_gpa_points_term,
            sum(potential_credit_hours_term) as credit_hours_term,
            round(
                safe_divide(
                    sum(potential_credit_hours_default * term_grade_points),
                    sum(potential_credit_hours_term)
                ),
                2
            ) as gpa_term,

            /* gpa Y1 */
            round(avg(y1_percent_grade_adjusted), 0) as grade_avg_y1,
            sum(y1_grade_points) as gpa_points_total_y1,
            sum(
                potential_credit_hours_default * y1_grade_points
            ) as weighted_gpa_points_y1,
            round(
                safe_divide(
                    sum(potential_credit_hours_default * y1_grade_points),
                    sum(potential_credit_hours_y1)
                ),
                2
            ) as gpa_y1,
            round(
                safe_divide(
                    sum(potential_credit_hours_default * y1_grade_points_unweighted),
                    sum(potential_credit_hours_y1)
                ),
                2
            ) as gpa_y1_unweighted,

            /* other */
            sum(potential_credit_hours_y1) as total_credit_hours,
            sum(if(y1_letter_grade like 'F%', 1, 0)) as n_failing_y1,
        from grade_detail
        group by studentid, yearid, storecode, is_current, schoolid
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
    total_credit_hours,
    grade_avg_term as grade_avg_term,
    grade_avg_y1 as grade_avg_y1,
    round(weighted_gpa_points_term, 2) as weighted_gpa_points_term,
    round(weighted_gpa_points_y1, 2) as weighted_gpa_points_y1,

    /* gpa semester */
    sum(gpa_points_total_term) over (
        partition by studentid, yearid, semester
    ) as gpa_points_total_semester,
    round(
        avg(grade_avg_term) over (partition by studentid, yearid, semester), 0
    ) as grade_avg_semester,
    round(
        sum(weighted_gpa_points_term) over (partition by studentid, yearid, semester), 2
    ) as weighted_gpa_points_semester,
    round(
        sum(total_credit_hours) over (partition by studentid, yearid, semester), 2
    ) as total_credit_hours_semester,
    round(
        sum(weighted_gpa_points_term) over (partition by studentid, yearid, semester)
        / sum(credit_hours_term) over (partition by studentid, yearid, semester),
        2
    ) as gpa_semester,
from grade_rollup
