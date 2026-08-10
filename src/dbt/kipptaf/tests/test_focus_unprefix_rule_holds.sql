-- Focus records the pre-migration student number on returning students, so it is
-- an independent check on the unprefix rule: stripping the 8400 prefix must land
-- on the same value Focus already stored. Warn rather than error, because the one
-- known anomalous id (a 10-digit value carrying no 8400 prefix) passes through
-- deliberately and is an Ops correction in Focus, not a modeling defect.
select student_number, powerschool_id,
from {{ ref("int_students__students") }}
where powerschool_id is not null and cast(powerschool_id as int64) != student_number
