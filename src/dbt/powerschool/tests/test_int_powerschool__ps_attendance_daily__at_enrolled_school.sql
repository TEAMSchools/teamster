select
    ad.id,
    ad.studentid,
    ad.att_date,
    ad.schoolid as attendance_schoolid,

    mr.schoolid as enrolled_schoolid,
from {{ ref("int_powerschool__ps_attendance_daily") }} as ad
inner join
    {{ ref("int_powerschool__ps_membership_reg") }} as mr
    on ad.studentid = mr.studentid
    and ad.att_date = mr.calendardate
where ad.schoolid != mr.schoolid
