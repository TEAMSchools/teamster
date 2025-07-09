with
    ada_week_values as (
        select
            mem._dbt_source_relation,
            mem.studentid,
            mem.yearid,
            mem.schoolid,

            w.week_start_monday,

            /* standard ada calcs */
            sum(mem.attendancevalue) as sum_attendance_value_week,
            count(mem.attendancevalue) as count_attendance_value_week,
            round(avg(mem.attendancevalue), 3) as ada_week,

            /* HS weighted ada cals */
            sum(
                if(
                    w.school_level = 'HS' and att.att_code like 'T%',
                    0.67,
                    mem.attendancevalue
                )
            ) as sum_attendance_value_week_weighted,
            round(
                avg(
                    if(
                        w.school_level = 'HS' and att.att_code like 'T%',
                        0.67,
                        mem.attendancevalue
                    )
                ),
                3
            ) as ada_week_weighted,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as mem
        left join
            {{ ref("int_powerschool__ps_attendance_daily") }} as att
            on mem.studentid = att.studentid
            and mem.calendardate = att.att_date
            and {{ union_dataset_join_clause(left_alias="mem", right_alias="att") }}
        inner join
            {{ ref("int_powerschool__calendar_week") }} as w
            on mem.schoolid = w.schoolid
            and mem.yearid = w.yearid
            and mem.calendardate between w.week_start_monday and w.week_end_sunday
        where
            membershipvalue = 1
            and calendardate <= current_date('{{ var("local_timezone") }}')
        group by all
    )

select
    _dbt_source_relation,
    studentid,
    yearid,
    schoolid,
    week_start_monday,
    ada_week,
    ada_week_weighted,

    (
        sum(sum_attendance_value_week) over (
            partition by
                _dbt_source_relation, studentid, yearid, schoolid, week_start_monday
            order by week_start_monday asc
        ) / sum(count_attendance_value_week) over (
            partition by
                _dbt_source_relation, studentid, yearid, schoolid, week_start_monday
            order by week_start_monday asc
        )
    ) as ada_week_running,

    round(
        (
            sum(sum_attendance_value_week_weighted) over (
                partition by _dbt_source_relation, studentid, yearid, schoolid
                order by week_start_monday asc
            ) / sum(count_attendance_value_week) over (
                partition by _dbt_source_relation, studentid, yearid, schoolid
                order by week_start_monday asc
            )
        ),
        3
    ) as ada_week_running_weighted,
from ada_week_values
