with
    agg_weeks as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            schoolid,
            week_start_monday,
            week_end_sunday,

            sum(attendancevalue) as attendance_value_sum,
            sum(membershipvalue) as membership_value_sum,
        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where
            attendancevalue is not null
            and calendardate >= '{{ var("current_academic_year") - 1 }}-07-01'
            and calendardate < current_date('{{ var("local_timezone") }}')
        group by
            _dbt_source_relation,
            studentid,
            academic_year,
            schoolid,
            week_start_monday,
            week_end_sunday
    )

select
    co.student_number,
    co.academic_year,
    co.week_start_monday,
    co.week_end_sunday,

    sum(agg.attendance_value_sum) over (
        partition by co.studentid, co.academic_year, co.schoolid
        order by co.week_start_monday asc
    ) as attendance_value_sum_running,

    sum(agg.membership_value_sum) over (
        partition by co.studentid, co.academic_year, co.schoolid
        order by co.week_start_monday asc
    ) as membership_value_sum_running,

    round(
        safe_divide(
            sum(agg.attendance_value_sum) over (
                partition by co.studentid, co.academic_year, co.schoolid
                order by co.week_start_monday asc
            ),
            sum(agg.membership_value_sum) over (
                partition by co.studentid, co.academic_year, co.schoolid
                order by co.week_start_monday asc
            )
        ),
        3
    ) as ada_running,
from {{ ref("int_extracts__student_enrollments_weeks") }} as co
left join
    agg_weeks as agg
    on co.studentid = agg.studentid
    and co.schoolid = agg.schoolid
    and co.academic_year = agg.academic_year
    and co.week_start_monday = agg.week_start_monday
where co.academic_year >= {{ var("current_academic_year") - 1 }}
