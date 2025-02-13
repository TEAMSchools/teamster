select
    _dbt_source_relation,
    cc_academic_year,
    cc_schoolid,
    cc_studentid,
    students_student_number,
    courses_course_number,
    courses_course_name,
    cc_dateenrolled,
    cc_dateleft,
    ap_course_subject,
    is_ap_course,
    nces_subject_area,
    nces_course_id,

    rn_credittype_year,
    rn_course_number_year,

    concat(nces_subject_area, nces_subject_area) as sced_code,

    if(
        cc_dateenrolled <= '2023-10-02' and cc_dateleft >= '2023-10-02', true, false
    ) as oct_01_course,

from {{ ref("base_powerschool__course_enrollments") }}
where cc_academic_year = 2023
