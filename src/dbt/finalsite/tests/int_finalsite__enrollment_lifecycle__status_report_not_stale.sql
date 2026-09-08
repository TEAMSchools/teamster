-- Detects a stale-read build of int_finalsite__enrollment_lifecycle: the model
-- joins contacts (Finalsite API) to the status report (SFTP drop), which rebuild
-- in separate concurrent Dagster runs, so the table can be built from a status
-- report older than the one now on disk. Either gate column then comes back
-- null while the live status report already holds a value, and downstream the
-- Focus enrollment extract drops the student with no error anywhere. Every row
-- here is an enrollment the next delivery will omit. Refs #4834.
with
    status_report_latest as (
        {{
            dbt_utils.deduplicate(
                relation=ref("stg_finalsite__status_report"),
                partition_by="finalsite_enrollment_id",
                order_by="_dagster_partition_key desc",
            )
        }}
    )

select
    l.finalsite_enrollment_id,
    l.enrollment_start_date,
    l.assigned_school,
    sr.enrolled_date as status_report_enrolled_date,
    sr.assigned_school as status_report_assigned_school,
from {{ ref("int_finalsite__enrollment_lifecycle") }} as l
inner join
    status_report_latest as sr on l.finalsite_enrollment_id = sr.finalsite_enrollment_id
where
    (l.enrollment_start_date is null and sr.enrolled_date is not null)
    or (l.assigned_school is null and sr.assigned_school is not null)
