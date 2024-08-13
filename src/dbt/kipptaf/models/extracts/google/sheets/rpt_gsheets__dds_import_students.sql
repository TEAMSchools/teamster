select
    student_last as `last`,
    student_first as `first`,
    students_student_number as studentid,
    school_name as incoming_school,
    grade_level as incoming_grade,
    class_name as incoming_classname,

    null as dob,
from {{ ref("int_gsheets__dds_import") }}
