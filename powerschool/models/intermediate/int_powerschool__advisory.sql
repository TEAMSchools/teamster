with
    hr_enrollments as (
        select
            cc_studentid as studentid,
            cc_yearid as yearid,
            cc_schoolid as schoolid,
            cc_dateenrolled,
            cc_dateleft,
            teachernumber as teachernumber,
            is_dropped_section,
            sections_section_number,
            teacher_lastfirst,
        from {{ ref("base_powerschool__course_enrollments") }}
        where cc_course_number = 'HR' and not is_dropped_course
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="hr_enrollments",
                partition_by="studentid, yearid, schoolid",
                order_by="is_dropped_section asc, cc_dateleft desc, cc_dateenrolled desc",
            )
        }}
    )

select
    studentid,
    yearid,
    schoolid,
    teachernumber as advisor_teachernumber,
    teacher_lastfirst as advisor_lastfirst,
    coalesce(
        nullif(regexp_extract(sections_section_number, r'(\D+)'), ''), teacher_lastfirst
    ) as advisory_name,
from deduplicate
