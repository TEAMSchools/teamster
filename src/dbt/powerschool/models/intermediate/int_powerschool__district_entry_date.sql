with
    district_entry as (
        select
            studentid,
            student_number,
            entrycode,
            exitcode,
            entrydate,
            exitdate,

            lag(exitcode, 1) over (
                partition by studentid order by entrydate asc
            ) as exitcode_prev,
        from {{ ref("base_powerschool__student_enrollments") }}
        where schoolid != 999999
    )

select
    de.studentid,
    de.student_number,
    de.entrydate,
    de.exitdate,
    de.entrycode,
    de.exitcode_prev,

    min(att.calendardate) as district_entry_date,

    row_number() over (
        partition by de.studentid order by de.entrydate desc
    ) as rn_entry,
from district_entry as de
inner join
    {{ ref("int_powerschool__ps_adaadm_daily_ctod") }} as att
    on de.studentid = att.studentid
    and att.calendardate between de.entrydate and de.exitdate
    and att.membershipvalue = 1
    and att.attendancevalue = 1
where
    (de.exitcode_prev is null or de.exitcode_prev not in ('T1', 'T2'))
    and (de.entrycode is null or de.entrycode not in ('R1', 'R2'))
group by
    de.studentid,
    de.student_number,
    de.entrycode,
    de.exitcode,
    de.exitcode_prev,
    de.entrydate,
    de.exitdate
