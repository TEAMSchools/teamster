select
    sced_code,
    sced_course_name,
    crdc_course_group,
    crdc_subject_group,
    crdc_ap_group,
    ap_tag,
    duplicate,
from {{ source("crdc", "src_crdc__sced_code_crosswalk") }}
