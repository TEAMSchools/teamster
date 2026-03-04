select
    * except (
        assignment_filter_yn,
        calculate_ada_yn,
        calculate_adm_yn,
        course_credit_points,
        dcid,
        id,
        schoolid,
        sortorder,
        yearid,
        lock_teacher_yn,
        source_file_name
    ),

    cast(dcid as int) as dcid,
    cast(id as int) as id,
    cast(assignment_filter_yn as int) as assignment_filter_yn,
    cast(calculate_ada_yn as int) as calculate_ada_yn,
    cast(calculate_adm_yn as int) as calculate_adm_yn,
    cast(schoolid as int) as schoolid,
    cast(sortorder as int) as sortorder,
    cast(yearid as int) as yearid,
    cast(lock_teacher_yn as int) as lock_teacher_yn,

    cast(course_credit_points as float64) as course_credit_points,
from {{ source("powerschool_sftp", "src_powerschool__attendance_code") }}
