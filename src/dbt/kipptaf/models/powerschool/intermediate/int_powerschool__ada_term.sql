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
    _dbt_source_relation,
    studentid,
    academic_year,
    yearid,
    semester,
    term,

    avg(attendancevalue) over (
        partition by _dbt_source_relation, yearid, studentid, term
    ) as ada_term,

    avg(attendancevalue) over (
        partition by _dbt_source_relation, yearid, studentid, semester
    ) as ada_semester,

    avg(attendancevalue) over (
        partition by _dbt_source_relation, yearid, studentid
    ) as ada_year,

from membership_days
qualify
    row_number() over (
        partition by _dbt_source_relation, studentid, yearid, term order by calendardate
    )
    = 1
