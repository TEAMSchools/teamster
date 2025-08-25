select
    * except (
        assignment_filter_yn,
        calculate_ada_yn,
        calculate_adm_yn,
        course_credit_points,
        dcid,
        id,
        lock_teacher_yn,
        schoolid,
        sortorder,
        yearid
    ),

    /* column transformations */
    assignment_filter_yn.int_value as assignment_filter_yn,
    calculate_ada_yn.int_value as calculate_ada_yn,
    calculate_adm_yn.int_value as calculate_adm_yn,
    dcid.int_value as dcid,
    id.int_value as id,
    lock_teacher_yn.int_value as lock_teacher_yn,
    schoolid.int_value as schoolid,
    sortorder.int_value as sortorder,
    yearid.int_value as yearid,

    course_credit_points.double_value as course_credit_points,
from {{ source("powerschool_odbc", "src_powerschool__attendance_code") }}
