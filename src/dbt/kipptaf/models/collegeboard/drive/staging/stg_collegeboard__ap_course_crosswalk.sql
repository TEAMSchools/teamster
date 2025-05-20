select
    * except (ps_ap_course_subject_code),

    cast(ps_ap_course_subject_code as string) as ps_ap_course_subject_code,
from {{ source("collegeboard", "src_collegeboard__ap_course_crosswalk") }}
