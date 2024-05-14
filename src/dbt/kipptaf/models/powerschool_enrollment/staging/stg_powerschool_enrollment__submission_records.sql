select
    sr.externalstudentid as external_student_id,
    sr.firstname as first_name,
    sr.lastname as last_name,
    sr.status,
    sr.school,
    sr.grade,

    sr.tags,

    di.key as data_item_key,

    safe_cast(sr._dagster_partition_key as int) as published_action_id,
    safe_cast(sr.id as int) as id,

    nullif(sr.externalfamilyid, '') as external_family_id,
    nullif(sr.household, '') as household,
    nullif(sr.enrollstatus, '') as enroll_status,

    date(sr.dateofbirth) as date_of_birth,
    datetime(sr.imported) as `imported`,
    datetime(sr.started) as `started`,
    datetime(sr.submitted) as submitted,

    nullif(di.value, '') as data_item_value,
from
    {{
        source(
            "powerschool_enrollment", "src_powerschool_enrollment__submission_records"
        )
    }} as sr
cross join unnest(sr.dataitems) as di
