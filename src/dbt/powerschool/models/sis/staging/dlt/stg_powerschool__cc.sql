with
    staging as (
        select
            section_number,
            course_number,

            cast(id as int) as id,
            cast(dcid as int) as dcid,
            cast(studentid as int) as studentid,
            cast(sectionid as int) as sectionid,
            cast(schoolid as int) as schoolid,
            cast(studyear as int) as studyear,
            cast(termid as int) as termid,
            cast(dateenrolled as date) as dateenrolled,
            cast(dateleft as date) as dateleft,
            cast(teacherid as int) as teacherid,
            cast(currentabsences as int) as currentabsences,
            cast(currenttardies as int) as currenttardies,
        from {{ source("powerschool_dlt", "cc") }}
    ),

    calcs as (
        select
            *,

            cast(left(cast(abs(termid) as string), 2) as int) as yearid,

            abs(termid) as abs_termid,
            abs(sectionid) as abs_sectionid,
        from staging
    )

select *, yearid + 1990 as academic_year, yearid + 1991 as fiscal_year,
from calcs
