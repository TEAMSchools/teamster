with
    ada_by_term as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            semester,
            term,

            sum(is_present_weighted) as sum_attendance_value_weighted_term,
            sum(attendancevalue) as sum_attendance_value_term,
            sum(membershipvalue) as sum_membership_value_term,

            count(attendancevalue) as count_attendance_value_term,

            avg(attendancevalue) as ada_term,

            sum(abs(attendancevalue - 1)) as sum_absences_term,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where
            membershipvalue = 1
            and attendancevalue is not null
            and calendardate <= current_date('{{ var("local_timezone") }}')
        group by _dbt_source_relation, studentid, academic_year, semester, term
    )

select
    _dbt_source_relation,
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
                partition by _dbt_source_relation, studentid, academic_year, semester
            ),
            sum(count_attendance_value_term) over (
                partition by _dbt_source_relation, studentid, academic_year, semester
            )
        ),
        3
    ) as ada_semester,

    round(
        safe_divide(
            sum(sum_attendance_value_term) over (
                partition by _dbt_source_relation, studentid, academic_year
            ),
            sum(count_attendance_value_term) over (
                partition by _dbt_source_relation, studentid, academic_year
            )
        ),
        3
    ) as ada_year,

    round(
        safe_divide(
            sum(sum_attendance_value_term) over (
                partition by _dbt_source_relation, studentid, academic_year
                order by term asc
            ),
            sum(count_attendance_value_term) over (
                partition by _dbt_source_relation, studentid, academic_year
                order by term asc
            )
        ),
        3
    ) as ada_year_running,

    round(sum_attendance_value_weighted_term, 3) as ada_weighted_term,

    round(
        safe_divide(
            sum(sum_attendance_value_weighted_term) over (
                partition by _dbt_source_relation, studentid, academic_year, semester
            ),
            sum(count_attendance_value_term) over (
                partition by _dbt_source_relation, studentid, academic_year, semester
            )
        ),
        3
    ) as ada_weighted_semester,

    round(
        safe_divide(
            sum(sum_attendance_value_weighted_term) over (
                partition by _dbt_source_relation, studentid, academic_year
            ),
            sum(count_attendance_value_term) over (
                partition by _dbt_source_relation, studentid, academic_year
            )
        ),
        3
    ) as ada_weighted_year,

    round(
        safe_divide(
            sum(sum_attendance_value_weighted_term) over (
                partition by _dbt_source_relation, studentid, academic_year
                order by term asc
            ),
            sum(count_attendance_value_term) over (
                partition by _dbt_source_relation, studentid, academic_year
                order by term asc
            )
        ),
        3
    ) as ada_weighted_year_running,

from ada_by_term
