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
    ),

    running_calcs as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,
            schoolid,
            week_start_monday,
            week_end_sunday,

            sum(attendance_value_sum) over (
                partition by studentid, academic_year, schoolid
                order by week_start_monday asc
            ) as attendance_value_sum_running,

            sum(membership_value_sum) over (
                partition by studentid, academic_year, schoolid
                order by week_start_monday asc
            ) as membership_value_sum_running,
        from agg_weeks
    )

select
    co.student_number,
    co.academic_year,

    rc.attendance_value_sum_running,
    rc.membership_value_sum_running,
    rc.week_start_monday,
    rc.week_end_sunday,

    round(
        safe_divide(attendance_value_sum_running, membership_value_sum_running), 3
    ) as ada_running,
from {{ ref("int_extracts__student_enrollments") }} as co
left join
    running_calcs as rc
    on co.studentid = rc.studentid
    and co.academic_year = rc.academic_year
    and co.schoolid = rc.schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="rc") }}
where co.academic_year >= {{ var("current_academic_year") - 1 }}
