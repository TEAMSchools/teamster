select _dbt_source_relation, yearid, studentid, avg(attendancevalue) as ada,
from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
where membershipvalue = 1 and calendardate <= current_date('America/New_York')
group by _dbt_source_relation, yearid, studentid
