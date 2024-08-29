with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("powerschool", "src_powerschool__cc"),
                partition_by="dcid.int_value",
                order_by="_file_name desc",
            )
        }}
    ),

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
        {#- attendance_type_code.int_value as attendance_type_code, #}
        {#- origsectionid.int_value as origsectionid, #}
        {#- unused2.int_value as unused2, #}
        {#- unused3.int_value as unused3, #}
        {#- whomodifiedid.int_value as whomodifiedid, #}
        from deduplicate
    ),

    calcs as (
        select
            dcid,
            id,
            studentid,
            sectionid,
            section_number,
            schoolid,
            studyear,
            termid,
            dateenrolled,
            dateleft,
            course_number,
            teacherid,
            currentabsences,
            currenttardies,

            abs(termid) as abs_termid,
            abs(sectionid) as abs_sectionid,

            safe_cast(left(cast(abs(termid) as string), 2) as int) as yearid,
        from staging
    )

select *, (yearid + 1990) as academic_year, (yearid + 1991) as fiscal_year,
from calcs
