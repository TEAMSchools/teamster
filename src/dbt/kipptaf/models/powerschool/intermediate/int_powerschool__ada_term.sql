with
    term as (
        select
            t._dbt_source_relation,
            t.schoolid,
            t.yearid,

            tb.storecode as term,
            tb.date1 as term_start_date,
            tb.date2 as term_end_date,

            t.yearid + 1990 as academic_year,

            if(
                current_date('{{ var("local_timezone") }}')
                between tb.date1 and tb.date2,
                true,
                false
            ) as is_current_term,

            case
                when tb.storecode in ('Q1', 'Q2')
                then 'S1'
                when tb.storecode in ('Q3', 'Q4')
                then 'S2'
            end as semester,

        from {{ ref("stg_powerschool__terms") }} as t
        inner join
            {{ ref("stg_powerschool__termbins") }} as tb
            on t.id = tb.termid
            and t.schoolid = tb.schoolid
            and {{ union_dataset_join_clause(left_alias="t", right_alias="tb") }}
            and tb.storecode in ('Q1', 'Q2', 'Q3', 'Q4')
        where t.isyearrec = 1
    ),

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
        join
            term as t
            on a.yearid = t.yearid
            and a.schoolid = t.schoolid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="t") }}
        where
            a.membershipvalue = 1
            and a.calendardate <= t.term_end_date
            and a.calendardate <= current_date('{{ var("local_timezone") }}')

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

        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as a
        inner join
            term as t
            on a.yearid = t.yearid
            and a.schoolid = t.schoolid
            and {{ union_dataset_join_clause(left_alias="a", right_alias="t") }}
            and a.calendardate >= t.term_start_date
            and a.calendardate <= t.term_end_date
        where
            a.membershipvalue = 1
            and a.calendardate <= current_date('{{ var("local_timezone") }}')
    )

select
    m._dbt_source_relation,
    m.studentid,
    m.academic_year,
    m.yearid,
    m.semester,
    m.term,

    r.running_ada_year_term,

    avg(m.attendancevalue) over (
        partition by m._dbt_source_relation, m.yearid, m.studentid, m.term
    ) as ada_term,

    avg(m.attendancevalue) over (
        partition by m._dbt_source_relation, m.yearid, m.studentid, m.semester
    ) as ada_semester,

    avg(m.attendancevalue) over (
        partition by m._dbt_source_relation, m.yearid, m.studentid
    ) as ada_year,

    row_number() over (
        partition by m._dbt_source_relation, m.studentid, m.yearid, m.term
        order by m.calendardate
    ) as rn,

from membership_days as m
left join
    running_ada_by_term as r
    on m.yearid = r.yearid
    and m.studentid = r.studentid
    and {{ union_dataset_join_clause(left_alias="m", right_alias="r") }}
qualify rn = 1
