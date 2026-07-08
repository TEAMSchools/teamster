with
    status_report_latest as (
        {{
            dbt_utils.deduplicate(
                relation=ref("stg_finalsite__status_report"),
                partition_by="finalsite_enrollment_id",
                order_by="_dagster_partition_key desc",
            )
        }}
    ),

    contacts as (
        select
            finalsite_enrollment_id,
            status as finalsite_status,
            school_year_start,
            grade_canonical_name,
        from {{ ref("stg_finalsite__contacts") }}
    ),

    dated as (
        select
            c.finalsite_enrollment_id,
            c.finalsite_status,
            c.school_year_start,
            c.grade_canonical_name,

            sr.assigned_school,
            sr.enrolled_date as enrollment_start_date,

            trk.promotion_status_ss as promotion_status,

            -- withdrawal_last_attended_date (a Finalsite custom attribute) is the
            -- official signal that a student withdrew. Count it only when it is
            -- populated AND on/after the current enrollment start — a date before
            -- enrolled_date belongs to a prior enrollment on this reused contact,
            -- so a forward (re)enrollment never inherits a stale withdrawal.
            if(
                safe_cast(cca.withdrawal_last_attended_date as date)
                >= sr.enrolled_date,
                safe_cast(cca.withdrawal_last_attended_date as date),
                cast(null as date)
            ) as enrollment_end_date,
        from contacts as c
        left join
            status_report_latest as sr
            on c.finalsite_enrollment_id = sr.finalsite_enrollment_id
        left join
            {{ ref("int_finalsite__contact_track_attributes") }} as trk
            on c.finalsite_enrollment_id = trk.finalsite_enrollment_id
        left join
            {{ ref("int_finalsite__contact_custom_attributes") }} as cca
            on c.finalsite_enrollment_id = cca.finalsite_enrollment_id
    )

select
    finalsite_enrollment_id,
    school_year_start,
    grade_canonical_name,
    promotion_status,
    assigned_school,
    enrollment_start_date,
    enrollment_end_date,

    (
        enrollment_start_date is not null and enrollment_end_date is not null
    ) as is_transfer_out,
from dated
where
    finalsite_status
    in ('accepted', 'enrollment_in_progress', 'assigned_school', 'enrolled', 'retained')
    or (enrollment_start_date is not null and enrollment_end_date is not null)
