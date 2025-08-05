select
    studentid,
    yearid,

    sum(membershipvalue) as days_in_membership,
    sum(attendancevalue) as days_present,
    sum(abs(attendancevalue - 1)) as days_absent_unexcused,

    avg(attendancevalue) as ada,
from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
where
    membershipvalue = 1 and calendardate <= current_date('{{ var("local_timezone") }}')
group by yearid, studentid
