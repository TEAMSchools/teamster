select
    enr.cc_studentid as studentid,
    enr.cc_student_number as student_number,
    enr.cc_academic_year as academic_year,
    enr.cc_schoolid as schoolid,
    enr.cc_teachernumber as teachernumber,
    enr.cc_teacher_name as teacher_name,
    enr.cc_dateenrolled as dateenrolled,
    enr.cc_dateleft as dateleft,

    {# from  staff_crosswalk #}
    null as advisor_phone,
    null as advisor_email,
from {{ ref("base_powerschool__course_enrollments") }} as enr
where enr.cc_course_number = 'HR' and enr.rn_course_number_year = 1
