with
    daily_attendance as (
        select
            _dbt_source_project,
            student_number,
            studentid,
            academic_year,
            semester,
            term,

            /* NUMERIC rather than the source FLOAT64. A distributed float sum has no
               guaranteed association order, so a rate landing on a 3-decimal rounding
               midpoint rounds up in one evaluation and down in the next -- the same
               student-year disagreeing with itself across terms of the same window.
               Exact decimal addition is order-independent, which makes every rate
               below reproducible. The final select casts back to FLOAT64, so the
               model's output types are unchanged. */
            cast(attendancevalue as numeric) as attendancevalue,
            cast(is_present_weighted as numeric) as is_present_weighted,
            cast(membershipvalue as numeric) as membershipvalue,

        from {{ ref("int_students__attendance_daily") }}
        where
            membershipvalue = 1
            and attendancevalue is not null
            and calendardate <= current_date('{{ var("local_timezone") }}')
    ),

    -- Keyed on student_number, not studentid: studentid is a PowerSchool-internal
    -- id and is null for every Focus-sourced (Miami) row, so grouping on it
    -- collapses every Miami Focus student into one meaningless aggregate row per
    -- (kippmiami, academic_year, semester, term) -- SQL treats null as a single
    -- group. studentid is carried through as max(studentid) so the NJ-only
    -- downstream consumers that join on it keep working untouched; it stays null
    -- for Focus rows, which is correct.
    ada_by_term as (
        select
            _dbt_source_project,
            student_number,
            academic_year,
            semester,
            term,

            max(studentid) as studentid,

            sum(is_present_weighted) as sum_attendance_value_weighted_term,
            sum(attendancevalue) as sum_attendance_value_term,
            sum(membershipvalue) as sum_membership_value_term,

            count(attendancevalue) as count_attendance_value_term,

            avg(attendancevalue) as ada_term,

            sum(abs(attendancevalue - 1)) as sum_absences_term,

        from daily_attendance
        group by _dbt_source_project, student_number, academic_year, semester, term
    ),

    ada_rates as (
        select
            _dbt_source_project,
            student_number,
            studentid,
            academic_year,
            term,
            sum_attendance_value_term,
            sum_attendance_value_weighted_term,
            sum_membership_value_term,
            sum_absences_term,
            count_attendance_value_term,

            round(ada_term, 3) as ada_term,

            round(
                safe_divide(
                    sum(sum_attendance_value_term) over (
                        partition by
                            _dbt_source_project, student_number, academic_year, semester
                    ),
                    sum(count_attendance_value_term) over (
                        partition by
                            _dbt_source_project, student_number, academic_year, semester
                    )
                ),
                3
            ) as ada_semester,

            round(
                safe_divide(
                    sum(sum_attendance_value_term) over (
                        partition by _dbt_source_project, student_number, academic_year
                    ),
                    sum(count_attendance_value_term) over (
                        partition by _dbt_source_project, student_number, academic_year
                    )
                ),
                3
            ) as ada_year,

            round(
                safe_divide(
                    sum(sum_attendance_value_term) over (
                        partition by _dbt_source_project, student_number, academic_year
                        order by term asc
                    ),
                    sum(count_attendance_value_term) over (
                        partition by _dbt_source_project, student_number, academic_year
                        order by term asc
                    )
                ),
                3
            ) as ada_year_running,

            round(
                safe_divide(
                    sum_attendance_value_weighted_term, count_attendance_value_term
                ),
                3
            ) as ada_weighted_term,

            round(
                safe_divide(
                    sum(sum_attendance_value_weighted_term) over (
                        partition by
                            _dbt_source_project, student_number, academic_year, semester
                    ),
                    sum(count_attendance_value_term) over (
                        partition by
                            _dbt_source_project, student_number, academic_year, semester
                    )
                ),
                3
            ) as ada_weighted_semester,

            round(
                safe_divide(
                    sum(sum_attendance_value_weighted_term) over (
                        partition by _dbt_source_project, student_number, academic_year
                    ),
                    sum(count_attendance_value_term) over (
                        partition by _dbt_source_project, student_number, academic_year
                    )
                ),
                3
            ) as ada_weighted_year,

            round(
                safe_divide(
                    sum(sum_attendance_value_weighted_term) over (
                        partition by _dbt_source_project, student_number, academic_year
                        order by term asc
                    ),
                    sum(count_attendance_value_term) over (
                        partition by _dbt_source_project, student_number, academic_year
                        order by term asc
                    )
                ),
                3
            ) as ada_weighted_year_running,

        from ada_by_term
    )

select
    _dbt_source_project,
    student_number,
    studentid,
    academic_year,
    term,
    count_attendance_value_term,

    cast(sum_attendance_value_term as float64) as sum_attendance_value_term,
    cast(
        sum_attendance_value_weighted_term as float64
    ) as sum_attendance_value_weighted_term,
    cast(sum_membership_value_term as float64) as sum_membership_value_term,
    cast(sum_absences_term as float64) as sum_absences_term,
    cast(ada_term as float64) as ada_term,
    cast(ada_semester as float64) as ada_semester,
    cast(ada_year as float64) as ada_year,
    cast(ada_year_running as float64) as ada_year_running,
    cast(ada_weighted_term as float64) as ada_weighted_term,
    cast(ada_weighted_semester as float64) as ada_weighted_semester,
    cast(ada_weighted_year as float64) as ada_weighted_year,
    cast(ada_weighted_year_running as float64) as ada_weighted_year_running,

from ada_rates
