select
    ev.studentid,
    ev.schoolid,
    ev.track as student_track,
    ev.fteid,
    ev.dflt_att_mode_code,
    ev.dflt_conversion_mode_code,
    ev.att_calccntpresentabsent,
    ev.att_intervalduration,
    ev.grade_level,
    ev.yearid,

    cd.date_value as calendardate,
    cd.a,
    cd.b,
    cd.c,
    cd.d,
    cd.e,
    cd.f,
    cd.bell_schedule_id,
    cd.cycle_day_id,

    bs.attendance_conversion_id,

    case
        when
            (ev.track = 'A' and cd.a = 1)
            or (ev.track = 'B' and cd.b = 1)
            or (ev.track = 'C' and cd.c = 1)
            or (ev.track = 'D' and cd.d = 1)
            or (ev.track = 'E' and cd.e = 1)
            or (ev.track = 'F' and cd.f = 1)
        then ev.membershipshare
        when ev.track is null
        then ev.membershipshare
        else 0
    end as studentmembership,
    case
        when
            (ev.track = 'A' and cd.a = 1)
            or (ev.track = 'B' and cd.b = 1)
            or (ev.track = 'C' and cd.c = 1)
            or (ev.track = 'D' and cd.d = 1)
            or (ev.track = 'E' and cd.e = 1)
            or (ev.track = 'F' and cd.f = 1)
        then cd.membershipvalue
        when ev.track is null
        then cd.membershipvalue
        else 0
    end as calendarmembership,
    case
        when
            (ev.track = 'A' and cd.a = 1)
            or (ev.track = 'B' and cd.b = 1)
            or (ev.track = 'C' and cd.c = 1)
            or (ev.track = 'D' and cd.d = 1)
            or (ev.track = 'E' and cd.e = 1)
            or (ev.track = 'F' and cd.f = 1)
        then 1
        when (ev.track is null)
        then 1
        else 0
    end as ontrack,
    case
        when
            (ev.track = 'A' and cd.a = 1)
            or (ev.track = 'B' and cd.b = 1)
            or (ev.track = 'C' and cd.c = 1)
            or (ev.track = 'D' and cd.d = 1)
            or (ev.track = 'E' and cd.e = 1)
            or (ev.track = 'F' and cd.f = 1)
        then 0
        when ev.track is null
        then 0
        else 1
    end as offtrack,
from {{ ref("int_powerschool__ps_enrollment_all") }} as ev
inner join
    {{ ref("stg_powerschool__calendar_day") }} as cd
    on ev.schoolid = cd.schoolid
    and cd.date_value between ev.entrydate and date_sub(ev.exitdate, interval 1 day)
inner join
    {{ ref("stg_powerschool__bell_schedule") }} as bs on cd.bell_schedule_id = bs.id
where cd.insession = 1
