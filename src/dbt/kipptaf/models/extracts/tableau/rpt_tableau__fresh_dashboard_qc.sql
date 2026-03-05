with
    pre_fs_rollover_checks as (
        select *, from {{ ref("int_students__finalsite_student_roster") }}
    )

select *,
from pre_fs_rollover_checks
