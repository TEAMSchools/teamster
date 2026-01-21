with
    submission_records as (
        select
            externalstudentid as external_student_id,
            firstname as first_name,
            lastname as last_name,
            `status`,
            school,
            grade,

            /* repeated */
            tags,

            /* repeated records */
            dataitems,

            cast(_dagster_partition_key as int) as published_action_id,
            cast(id as int) as id,
            cast(`imported` as datetime) as `imported`,
            cast(`started` as datetime) as `started`,
            cast(submitted as datetime) as submitted,

            cast(cast(dateofbirth as datetime) as date) as date_of_birth,

            nullif(externalfamilyid, '') as external_family_id,
            nullif(household, '') as household,
            nullif(enrollstatus, '') as enroll_status,
        from
            {{
                source(
                    "powerschool_enrollment",
                    "src_powerschool_enrollment__submission_records",
                )
            }}
    )

select
    sr.* except (dataitems),

    di.key as data_item_key,

    nullif(di.value, '') as data_item_value,

    {{
        date_to_fiscal_year(
            date_field="sr.submitted", start_month=7, year_source="start"
        )
    }} as academic_year,
from submission_records as sr
cross join unnest(sr.dataitems) as di
