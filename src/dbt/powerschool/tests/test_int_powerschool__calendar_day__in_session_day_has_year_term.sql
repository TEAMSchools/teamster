select schoolid, date_value, school_name,
from {{ ref("int_powerschool__calendar_day") }}
where academic_year is null and insession = 1 and schoolid not in (0, 999999)
