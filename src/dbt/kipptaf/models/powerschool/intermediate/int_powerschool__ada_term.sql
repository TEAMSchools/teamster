with
    ada_by_term as (
        select
            a._dbt_source_relation,
            a.studentid,

            t.academic_year,
            t.semester,
            t.term,

            sum(a.attendancevalue) as sum_attendance_value_term,
            count(a.attendancevalue) as count_attendance_value_term,
            avg(a.attendancevalue) as ada_term,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as a
        inner join
            {{ ref("int_powerschool__terms") }} as t
            on a.yearid = t.yearid
            and a.schoolid = t.schoolid
            and a.calendardate between t.term_start_date and t.term_end_date
            and {{ union_dataset_join_clause(left_alias="a", right_alias="t") }}
        where
            a.membershipvalue = 1
            and a.calendardate <= current_date('{{ var("local_timezone") }}')
        group by
            a._dbt_source_relation, a.studentid, t.academic_year, t.semester, t.term
    )

select
    _dbt_source_relation,
    studentid,
    academic_year,
    term,
    ada_term,

    (
        (
            sum(sum_attendance_value_term) over (
                partition by _dbt_source_relation, studentid, academic_year, semester
            )
        ) / (
            sum(count_attendance_value_term) over (
                partition by _dbt_source_relation, studentid, academic_year, semester
            )
        )
    ) as ada_semester,

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
    ) as ada_year,

    (
        (
            sum(sum_attendance_value_term) over (
                partition by _dbt_source_relation, studentid, academic_year
                order by term asc
            )
        ) / (
            sum(count_attendance_value_term) over (
                partition by _dbt_source_relation, studentid, academic_year
                order by term asc
            )
        )
    ) as ada_year_running,
from ada_by_term
