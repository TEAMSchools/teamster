{{ config(enabled=(var("powerschool_external_source_type") == "odbc")) }}

select
    de_course_name,
    de_semester,
    whocreated,
    whencreated,
    whomodified,
    whenmodified,
    de_score,
    de_institution,

    id.int_value as id,
    storedgradesdcid.int_value as storedgradesdcid,
    de_pass_yn.int_value as de_pass_yn,
from {{ source("powerschool_odbc", "src_powerschool__u_storedgrades_de") }}
