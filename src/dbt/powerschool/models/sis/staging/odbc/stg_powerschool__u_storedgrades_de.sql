select
    de_course_name,
    de_semester,
    de_score,
    de_institution,

    de_pass_yn.int_value as de_pass_yn,
    id.int_value as id,
    storedgradesdcid.int_value as storedgradesdcid,
from {{ source("powerschool_odbc", "src_powerschool__u_storedgrades_de") }}
