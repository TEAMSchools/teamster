with
    ada_by_term as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            semester,
            quarter,

            sum(is_present_weighted) as sum_attendance_value_term_weighted,
            sum(attendancevalue) as sum_attendance_value_term,
            count(attendancevalue) as count_attendance_value_term,
            round(avg(is_present), 3) as ada_term,
        from {{ ref("int_powerschool__ada_detail") }}
        where calendardate <= current_date('{{ var("local_timezone") }}')
        group by _dbt_source_relation, studentid, academic_year, semester, quarter
    )

select
    _dbt_source_relation,
    studentid,
    academic_year,
    quarter,
    ada_term,

    round(
        (
            (
                sum(sum_attendance_value_term) over (
                    partition by
                        _dbt_source_relation, studentid, academic_year, semester
                )
            ) / (
                sum(count_attendance_value_term) over (
                    partition by
                        _dbt_source_relation, studentid, academic_year, semester
                )
            )
        ),
        3
    ) as ada_semester,

    round(
        (
            (
                sum(sum_attendance_value_term) over (
                    partition by _dbt_source_relation, studentid, academic_year
                )
            ) / (
                sum(count_attendance_value_term) over (
                    partition by _dbt_source_relation, studentid, academic_year
                )
            )
        ),
        3
    ) as ada_year,

    round(
        (
            (
                sum(sum_attendance_value_term) over (
                    partition by _dbt_source_relation, studentid, academic_year
                    order by quarter asc
                )
            ) / (
                sum(count_attendance_value_term) over (
                    partition by _dbt_source_relation, studentid, academic_year
                    order by quarter asc
                )
            )
        ),
        3
    ) as ada_quarter_running,

    round(
        (
            (
                sum(sum_attendance_value_term_weighted) over (
                    partition by _dbt_source_relation, studentid, academic_year
                    order by quarter asc
                )
            ) / (
                sum(count_attendance_value_term) over (
                    partition by _dbt_source_relation, studentid, academic_year
                    order by quarter asc
                )
            )
        ),
        3
    ) as ada_quarter_running_weighted,
from ada_by_term
