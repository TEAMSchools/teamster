select
    * except (
        dcid,
        id,
        schoolid,
        yearid,
        course_credit_points,
        assignment_filter_yn,
        calculate_ada_yn,
        calculate_adm_yn,
        sortorder
    ),

    /* column transformations */
    dcid.int_value as dcid,
    id.int_value as id,
    schoolid.int_value as schoolid,
    yearid.int_value as yearid,
    course_credit_points.double_value as course_credit_points,
    assignment_filter_yn.int_value as assignment_filter_yn,
    calculate_ada_yn.int_value as calculate_ada_yn,
    calculate_adm_yn.int_value as calculate_adm_yn,
    sortorder.int_value as sortorder,
from {{ source("powerschool", "src_powerschool__attendance_code") }}
