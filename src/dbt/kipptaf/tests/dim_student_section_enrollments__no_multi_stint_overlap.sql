with
    student_enrollments as (
        select studentid, schoolid, yearid, entrydate, exitdate, _dbt_source_project,
        from {{ ref("int_powerschool__student_enrollment_union") }}
        where entrydate is not null and exitdate is not null
    )

select cc.cc_dcid, cc._dbt_source_project, count(*) as n_overlapping_stints,
from {{ ref("base_powerschool__course_enrollments") }} as cc
inner join
    student_enrollments as enr
    on cc.cc_studentid = enr.studentid
    and cc.sections_schoolid = enr.schoolid
    and cc.cc_yearid = enr.yearid
    and cc._dbt_source_project = enr._dbt_source_project
    and cc.cc_dateleft > enr.entrydate
    and cc.cc_dateenrolled < enr.exitdate
where not cc.is_dropped_section
group by cc.cc_dcid, cc._dbt_source_project
having count(*) > 1
