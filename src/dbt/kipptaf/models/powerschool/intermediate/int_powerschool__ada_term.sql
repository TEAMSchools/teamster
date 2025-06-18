with
    running_ada_by_term as (
        select
            a._dbt_source_relation,
            a.studentid,
            a.yearid,
            t.academic_year,
            t.term,
            t.semester,
            t.term_end_date,

            avg(a.attendancevalue) as running_ada_year_term,

        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as a
        inner join
            {{ ref("int_powerschool__term") }} as t
            on a.yearid = t.yearid
            and a.schoolid = t.schoolid
            and a.membershipvalue = 1
            and a.calendardate
            between t.term_end_date and current_date('{{ var("local_timezone") }}')
            and {{ union_dataset_join_clause(left_alias="a", right_alias="t") }}
        group by
            a._dbt_source_relation,
            a.studentid,
            a.yearid,
            t.academic_year,
            t.term,
            t.semester,
            t.term_end_date
    ),

    membership_days as (
        select
            a._dbt_source_relation,
            a.yearid,
            a.studentid,
            a.attendancevalue,
            a.calendardate,

            t.academic_year,
            t.semester,
            t.term,

            r.running_ada_year_term,

        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as a
        inner join
            {{ ref("int_powerschool__term") }} as t
            on a.yearid = t.yearid
            and a.schoolid = t.schoolid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="t") }}
            and a.membershipvalue = 1
            and a.calendardate between t.term_start_date and t.term_end_date
            and a.calendardate <= current_date('{{ var("local_timezone") }}')
        inner join
            running_ada_by_term as r
            on a.yearid = r.yearid
            and a.studentid = r.studentid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="r") }}
            and t.term = r.term
            and {{ union_dataset_join_clause(left_alias="t", right_alias="r") }}
    )

select
    _dbt_source_relation,
    studentid,
    academic_year,
    yearid,
    semester,
    term,
    running_ada_year_term,

    avg(attendancevalue) over (
        partition by _dbt_source_relation, yearid, studentid, term
    ) as ada_term,

    avg(attendancevalue) over (
        partition by _dbt_source_relation, yearid, studentid, semester
    ) as ada_semester,

    avg(attendancevalue) over (
        partition by _dbt_source_relation, yearid, studentid
    ) as ada_year,

    row_number() over (
        partition by _dbt_source_relation, studentid, yearid, term order by calendardate
    ) as rn,

from membership_days
qualify rn = 1
