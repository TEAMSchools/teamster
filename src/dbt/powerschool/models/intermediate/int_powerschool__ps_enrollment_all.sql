with
    union_relations as (
        select
            id,
            schoolid,
            entrydate,
            entrycode,
            exitdate,
            exitcode,
            grade_level,
            fteid,
            membershipshare,
            track,

            -1 as programid,
        from {{ ref("stg_powerschool__students") }}

        union distinct

        select
            studentid,
            schoolid,
            entrydate,
            entrycode,
            exitdate,
            exitcode,
            grade_level,
            fteid,
            membershipshare,
            track,

            -1 as programid,
        from {{ ref("stg_powerschool__reenrollments") }}
    )

select
    sr.id as studentid,
    sr.schoolid,
    sr.entrydate,
    sr.entrycode,
    sr.exitdate,
    sr.exitcode,
    sr.grade_level,
    sr.programid,
    sr.fteid,
    sr.membershipshare,
    sr.track,

    t.yearid,

    coalesce(f.dflt_att_mode_code, '-1') as dflt_att_mode_code,
    coalesce(f.dflt_conversion_mode_code, '-1') as dflt_conversion_mode_code,

    safe_cast(p2.value as string) as att_intervalduration,

    if(p.value like 'P', 'Present', 'Absent') as att_calccntpresentabsent,
from union_relations as sr
left join {{ ref("stg_powerschool__fte") }} as f on sr.fteid = f.id
left join
    {{ ref("stg_powerschool__terms") }} as t
    on sr.schoolid = t.schoolid
    and t.isyearrec = 1
    and sr.entrydate between t.firstday and t.lastday
left join
    {{ ref("stg_powerschool__prefs") }} as p
    on sr.schoolid = p.schoolid
    and p.name = 'ATT_CalcCntPresentsAbsences'
    and t.yearid = p.yearid
left join
    {{ ref("stg_powerschool__prefs") }} as p2
    on sr.schoolid = p2.schoolid
    and t.yearid = p2.yearid
    and p2.name = 'ATT_IntervalDuration'
