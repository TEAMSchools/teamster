select
    mem._dbt_source_relation,
    mem.studentid,
    mem.schoolid,
    mem.calendardate,

    att.att_code,

    t.academic_year,
    t.semester,
    t.term as `quarter`,

    cw.week_start_monday,
    cw.week_end_sunday,

    mem.membershipvalue,
    mem.attendancevalue,

    cast(mem.attendancevalue as numeric) as is_present,
    if(att.att_code like 'T%', 0.67, mem.attendancevalue) as is_present_weighted,

    abs(mem.attendancevalue - 1) as is_absent,
    if(att.att_code like 'T%', 1, 0) as is_tardy,
    if(att.att_code like 'T%', 0.0, 1.0) as is_ontime,

    if(att.att_code in ('OS', 'OSS', 'OSSP', 'SHI'), 1.0, 0.0) as is_oss,
    if(att.att_code in ('S', 'ISS'), 1.0, 0.0) as is_iss,
    if(
        att.att_code in ('OS', 'OSS', 'OSSP', 'S', 'ISS', 'SHI'), 1.0, 0.0
    ) as is_suspended,
from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as mem
left join
    {{ ref("int_powerschool__ps_attendance_daily") }} as att
    on mem.studentid = att.studentid
    and mem.calendardate = att.att_date
    and {{ union_dataset_join_clause(left_alias="mem", right_alias="att") }}
inner join
    {{ ref("int_powerschool__terms") }} as t
    on mem.yearid = t.yearid
    and mem.schoolid = t.schoolid
    and mem.calendardate between t.term_start_date and t.term_end_date
    and {{ union_dataset_join_clause(left_alias="mem", right_alias="t") }}
inner join
    {{ ref("int_powerschool__calendar_week") }} as cw
    on mem.yearid = cw.yearid
    and mem.schoolid = cw.schoolid
    and mem.calendardate between cw.week_start_monday and cw.week_end_sunday
where
    mem.membershipvalue = 1
    and mem.attendancevalue is not null
    and mem.calendardate <= current_date('{{ var("local_timezone") }}')
