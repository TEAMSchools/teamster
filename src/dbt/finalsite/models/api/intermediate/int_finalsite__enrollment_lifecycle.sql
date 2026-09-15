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
            sr.mid_year_withdrawal_date,
            sr.summer_withdraw_date,

            trk.promotion_status_ss as promotion_status,

            safe_cast(
                cca.withdrawal_last_attended_date as date
            ) as withdrawal_last_attended_date,

            -- Finalsite reuses one contact record across enrollment cycles, so
            -- enrolled_date can still hold a prior cycle's value while the current
            -- cycle has none. A date before this cycle's applicant_date is that
            -- stale value, not an enrollment. A null applicant_date makes the
            -- comparison null, which leaves enrolled_date intact.
            if(
                sr.enrolled_date < sr.applicant_date,
                cast(null as date),
                sr.enrolled_date
            ) as enrollment_start_date,
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
    ),

    ended as (
        select
            finalsite_enrollment_id,
            finalsite_status,
            school_year_start,
            grade_canonical_name,
            assigned_school,
            promotion_status,
            enrollment_start_date,

            -- Any one of the three withdrawal signals ends the enrollment, so
            -- take the earliest. A date before the enrollment start belongs to a
            -- prior enrollment on this reused contact, so a forward
            -- (re)enrollment never inherits a stale withdrawal; a null start
            -- (a stale enrolled_date, above) leaves the enrollment unended.
            (
                select min(d),
                from
                    unnest(
                        [
                            withdrawal_last_attended_date,
                            mid_year_withdrawal_date,
                            summer_withdraw_date
                        ]
                    ) as d
                where d >= enrollment_start_date
            ) as enrollment_end_date,
        from dated
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
from ended
where
    finalsite_status
    in ('accepted', 'enrollment_in_progress', 'assigned_school', 'enrolled', 'retained')
    or (enrollment_start_date is not null and enrollment_end_date is not null)
