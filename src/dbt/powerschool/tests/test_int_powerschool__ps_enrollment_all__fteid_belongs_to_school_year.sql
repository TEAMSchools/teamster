select
    e.studentid,
    e.student_number,
    e.schoolid,
    e.yearid,
    e.fteid,
    f.schoolid as fte_schoolid,
    f.yearid as fte_yearid,
from {{ ref("int_powerschool__ps_enrollment_all") }} as e
left join {{ ref("stg_powerschool__fte") }} as f on e.fteid = f.id
where
    e.fteid is not null
    and (f.id is null or f.schoolid != e.schoolid or f.yearid != e.yearid)
