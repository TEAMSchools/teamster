select
    yearid,
    student_number,

    -- Null on the Focus side, projected so the kipptaf union matches the
    -- PowerSchool branch column for column.
    cast(null as int64) as studentid,
    yearid + 1990 as academic_year,

    sum(membershipvalue) as days_in_membership,
    sum(attendancevalue) as days_present,
    sum(abs(attendancevalue - 1)) as days_absent_unexcused,
    avg(attendancevalue) as ada,
from {{ ref("int_focus__attendance_daily") }}
where
    membershipvalue = 1 and calendardate <= current_date('{{ var("local_timezone") }}')
group by yearid, student_number
