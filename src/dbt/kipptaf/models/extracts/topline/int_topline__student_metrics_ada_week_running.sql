with
    school_level as (
        select powerschool_school_id as schoolid, max(grade_band) as grade_band,
        from {{ ref("stg_people__location_crosswalk") }}
        group by powerschool_school_id
    )

select
    mem.studentid,
    mem.yearid,
    mem.schoolid,

    w.week_start_monday,

    round(avg(mem.attendancevalue), 3) as ada_running,
    round(
        avg(
            if(
                sl.grade_band = 'HS' and att.att_code like 'T%',
                0.67,
                mem.attendancevalue
            )
        ),
        3
    ) as ada_running_weighted,
from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as mem
left join
    {{ ref("int_powerschool__ps_attendance_daily") }} as att
    on mem.studentid = att.studentid
    and mem.calendardate = att.att_date
    and {{ union_dataset_join_clause(left_alias="mem", right_alias="att") }}
inner join school_level as sl on mem.schoolid = sl.schoolid
inner join
    {{ ref("int_powerschool__calendar_week") }} as w
    on mem.schoolid = w.schoolid
    and mem.yearid = w.yearid
    and mem.calendardate <= w.week_end_sunday
where
    membershipvalue = 1 and calendardate <= current_date('{{ var("local_timezone") }}')
group by all
