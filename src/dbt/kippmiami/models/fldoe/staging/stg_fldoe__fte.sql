select
    school_number,
    student_id,
    florida_student_id,
    student_name,
    grade,
    _dagster_partition_survey as survey_number,

    cast(fte_capped as numeric) as fte_capped,
    cast(fte_uncapped as numeric) as fte_uncapped,

    _dagster_partition_school_year + 2000 as fiscal_year,
    _dagster_partition_school_year + 1999 as academic_year,
from {{ source("fldoe", "src_fldoe__fte") }}
