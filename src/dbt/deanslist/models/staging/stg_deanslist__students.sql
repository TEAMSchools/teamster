select
    _dagster_partition_key as school_id,
    studentid as student_id,

    cast(studentschoolid as int) as student_school_id,

    /* repeated fields*/
    customfields as custom_fields,
from {{ source("deanslist", "src_deanslist__students") }}
