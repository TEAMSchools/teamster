with
    pre_fs_rollover_checks as (
        select *, from {{ ref("int_students__finalsite_student_roster") }}
    )

-- this is still a wip, please disregard
select *,
from pre_fs_rollover_checks
