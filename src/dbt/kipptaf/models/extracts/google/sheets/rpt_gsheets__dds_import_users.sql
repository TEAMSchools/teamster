select distinct
    teacher_mail as username,

    null as temporary_password,
    'Class' as usertype,

    school_name as school,

    2 as permissions,

    teacher_last as `last`,
    teacher_first as `first`,
    teacher_mail as email,
from {{ ref("int_gsheets__dds_import") }}
