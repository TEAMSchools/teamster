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
            student_number,
        from {{ ref("stg_powerschool__students") }}
        -- enroll_status = 1 marks an invalid student record; exclude it (and any
        -- enrollment history attached to it) from all enrollment-derived models.
        where enroll_status != 1

        union distinct

        select
            r.studentid,
            r.schoolid,
            r.entrydate,
            r.entrycode,
            r.exitdate,
            r.exitcode,
            r.grade_level,
            r.fteid,
            r.membershipshare,
            r.track,

            s.student_number,
        from {{ ref("stg_powerschool__reenrollments") }} as r
        inner join
            {{ ref("stg_powerschool__students") }} as s
            on r.studentid = s.id
            and s.enroll_status != 1
    )

select
    sr.id as studentid,
    sr.student_number,
    sr.schoolid,
    sr.entrydate,
    sr.entrycode,
    sr.exitdate,
    sr.exitcode,
    sr.grade_level,
    sr.fteid,
    sr.membershipshare,
    sr.track,

    t.yearid,

    -1 as programid,

    coalesce(f.dflt_att_mode_code, '-1') as dflt_att_mode_code,
    coalesce(f.dflt_conversion_mode_code, '-1') as dflt_conversion_mode_code,

from union_relations as sr
left join {{ ref("stg_powerschool__fte") }} as f on sr.fteid = f.id
left join
    {{ ref("stg_powerschool__terms") }} as t
    on sr.schoolid = t.schoolid
    and t.isyearrec = 1
    and sr.entrydate between t.firstday and t.lastday
