select distinct
    class_name as classname,
    grade_level as grade,
    school_name as school,
    teacher_lastfirst as teacher,

    '{{ var("current_academic_year") }}-{{ var("current_academic_year") + 1 }}'
    as track,

    0 as classtype,

    teacher_mail as username,
from {{ ref("int_gsheets__dds_import") }}
