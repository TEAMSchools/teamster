with
    staging as (
        select
            * except (
                currentabsences,
                currenttardies,
                dcid,
                id,
                schoolid,
                sectionid,
                studentid,
                studyear,
                teacherid,
                termid
            ),

            currentabsences.int_value as currentabsences,
            currenttardies.int_value as currenttardies,
            dcid.int_value as dcid,
            id.int_value as id,
            schoolid.int_value as schoolid,
            sectionid.int_value as sectionid,
            studentid.int_value as studentid,
            studyear.int_value as studyear,
            teacherid.int_value as teacherid,
            termid.int_value as termid,
        from {{ source("powerschool", "src_powerschool__cc") }}
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
