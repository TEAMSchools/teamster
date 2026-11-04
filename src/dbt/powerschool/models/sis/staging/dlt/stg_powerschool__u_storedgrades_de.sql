select
    de_course_name,
    de_semester,
    de_score,
    de_institution,

    cast(de_pass_yn as int) as de_pass_yn,
    cast(id as int) as id,
    cast(storedgradesdcid as int) as storedgradesdcid,
from {{ source("powerschool_dlt", "u_storedgrades_de") }}
