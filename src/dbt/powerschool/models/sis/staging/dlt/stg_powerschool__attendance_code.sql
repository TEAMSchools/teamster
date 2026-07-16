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

    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(assignment_filter_yn as int) as assignment_filter_yn,
    cast(calculate_ada_yn as int) as calculate_ada_yn,
    cast(calculate_adm_yn as int) as calculate_adm_yn,
    cast(lock_teacher_yn as int) as lock_teacher_yn,
    cast(schoolid as int) as schoolid,
    cast(sortorder as int) as sortorder,
    cast(yearid as int) as yearid,

    cast(course_credit_points as float64) as course_credit_points,
from {{ source("powerschool_dlt", "attendance_code") }}
