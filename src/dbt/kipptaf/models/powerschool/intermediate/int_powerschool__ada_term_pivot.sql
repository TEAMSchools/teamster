select
    _dbt_source_relation,
    studentid,
    academic_year,

    /* pivot fields */
    round(ada_term_q1, 3) as ada_term_q1,
    round(ada_term_q2, 3) as ada_term_q2,
    round(ada_term_q3, 3) as ada_term_q3,
    round(ada_term_q4, 3) as ada_term_q4,
    round(ada_weighted_term_q1, 3) as ada_weighted_term_q1,
    round(ada_weighted_term_q2, 3) as ada_weighted_term_q2,
    round(ada_weighted_term_q3, 3) as ada_weighted_term_q3,
    round(ada_weighted_term_q4, 3) as ada_weighted_term_q4,
    round(ada_year_running_q1, 3) as ada_year_running_q1,
    round(ada_year_running_q2, 3) as ada_year_running_q2,
    round(ada_year_running_q3, 3) as ada_year_running_q3,
    round(ada_year_running_q4, 3) as ada_year_running_q4,
    round(ada_weighted_year_running_q1, 3) as ada_weighted_year_running_q1,
    round(ada_weighted_year_running_q2, 3) as ada_weighted_year_running_q2,
    round(ada_weighted_year_running_q3, 3) as ada_weighted_year_running_q3,
    round(ada_weighted_year_running_q4, 3) as ada_weighted_year_running_q4,

    round(coalesce(ada_semester_q2, ada_semester_q1), 3) as ada_semester_s1,
    round(coalesce(ada_semester_q4, ada_semester_q3), 3) as ada_semester_s2,
    round(coalesce(ada_year_q4, ada_year_q3, ada_year_q2, ada_year_q1), 3) as ada_year,

    round(
        coalesce(ada_weighted_semester_q2, ada_weighted_semester_q1), 3
    ) as ada_weighted_semester_s1,
    round(
        coalesce(ada_weighted_semester_q4, ada_weighted_semester_q3), 3
    ) as ada_weighted_semester_s2,
    round(
        coalesce(ada_year_q4, ada_year_q3, ada_year_q2, ada_year_q1), 3
    ) as ada_weighted_year,

    coalesce(sum_absences_term_q1, 0)
    + coalesce(sum_absences_term_q2, 0)
    + coalesce(sum_absences_term_q3, 0)
    + coalesce(sum_absences_term_q4, 0) as sum_absences_year,

from
    {{ ref("int_powerschool__ada_term") }} pivot (
        max(ada_term) as ada_term,
        max(ada_semester) as ada_semester,
        max(ada_year) as ada_year,
        max(ada_year_running) as ada_year_running,
        max(ada_weighted_term) as ada_weighted_term,
        max(ada_weighted_semester) as ada_weighted_semester,
        max(ada_weighted_year) as ada_weighted_year,
        max(ada_weighted_year_running) as ada_weighted_year_running,
        max(sum_attendance_value_term) as sum_attendance_value_term,
        max(sum_attendance_value_weighted_term) as sum_attendance_value_weighted_term,
        max(sum_membership_value_term) as sum_membership_value_term,
        max(sum_absences_term) as sum_absences_term,
        max(count_attendance_value_term) as count_attendance_value_term
        for term in ('Q1', 'Q2', 'Q3', 'Q4')
    )
