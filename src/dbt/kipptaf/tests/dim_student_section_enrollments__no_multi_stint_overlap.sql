with
    student_enrollments as (
        select
            student_number,
            schoolid,
            academic_year,
            entrydate,
            exitdate,
            _dbt_source_project,
        from {{ ref("int_students__student_enrollment_union") }}
        where entrydate is not null and exitdate is not null
    )

select cc.cc_dcid, cc._dbt_source_project, count(*) as n_overlapping_stints,
from {{ ref("int_students__course_enrollments") }} as cc
inner join
    student_enrollments as enr
    on cc.students_student_number = enr.student_number
    and cc.sections_schoolid = enr.schoolid
    and cc.cc_academic_year = enr.academic_year
    and cc._dbt_source_project = enr._dbt_source_project
    and coalesce(cc.cc_dateleft, cast('9999-12-31' as date)) > enr.entrydate
    and cc.cc_dateenrolled < enr.exitdate
where not coalesce(cc.is_dropped_section, false)
group by cc.cc_dcid, cc._dbt_source_project
having count(*) > 1
