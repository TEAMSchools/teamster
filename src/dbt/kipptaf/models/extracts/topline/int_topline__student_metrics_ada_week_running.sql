with
    ada_week_values as (
        select
            co.student_number,
            co.academic_year,
            co.schoolid,

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
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on mem.studentid = co.schoolid
            and mem.yearid = co.yearid
            and mem.schoolid = co.schoolid
            and mem.calendardate between co.entrydate and co.exitdate
            and {{ union_dataset_join_clause(left_alias="mem", right_alias="co") }}
        where
            membershipvalue = 1
            and calendardate <= current_date('{{ var("local_timezone") }}')
        group by co.student_number, co.academic_year, co.schoolid, w.week_start_monday
    )

select
    aw.student_number,
    aw.academic_year,
    aw.schoolid,
    aw.week_start_monday,
    aw.ada_week,
    aw.ada_week_weighted,

    round(
        (
            sum(aw.sum_attendance_value_week) over (
                partition by aw.student_number, aw.academic_year, aw.schoolid
                order by aw.week_start_monday asc
            ) / sum(aw.count_attendance_value_week) over (
                partition by aw.student_number, aw.academic_year, aw.schoolid
                order by week_start_monday asc
            )
        ),
        3
    ) as ada_week_running,

    round(
        (
            sum(sum_attendance_value_week_weighted) over (
                partition by student_number, academic_year, schoolid
                order by week_start_monday asc
            ) / sum(count_attendance_value_week) over (
                partition by student_number, academic_year, schoolid
                order by week_start_monday asc
            )
        ),
        3
    ) as ada_week_running_weighted,

    round(
        (
            sum(aw.sum_attendance_value_week) over (
                partition by aw.student_number, aw.academic_year
                order by aw.week_start_monday asc
            ) / sum(aw.count_attendance_value_week) over (
                partition by aw.student_number, aw.academic_year
                order by week_start_monday asc
            )
        ),
        3
    ) as ada_week_running_all_enrollments,

    round(
        (
            sum(sum_attendance_value_week_weighted) over (
                partition by student_number, academic_year
                order by week_start_monday asc
            ) / sum(count_attendance_value_week) over (
                partition by student_number, academic_year
                order by week_start_monday asc
            )
        ),
        3
    ) as ada_week_running_weighted_all_enrollments,
from ada_week_values as aw
