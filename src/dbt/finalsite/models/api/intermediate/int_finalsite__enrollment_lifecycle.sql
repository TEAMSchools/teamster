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
            enrollment_type,
            school_year_start,
            grade_canonical_name,

            (
                select max(t.value.string_value),
                from unnest(track_attributes) as t
                where t.field_name = 'promotion_status_ss'
            ) as promotion_status,
        from {{ ref("stg_finalsite__contacts") }}
    ),

    dated as (
        select
            c.finalsite_enrollment_id,
            c.finalsite_status,
            c.enrollment_type,
            c.school_year_start,
            c.grade_canonical_name,
            c.promotion_status,

            sr.assigned_school,
            sr.enrolled_date as enrollment_start_date,

            (
                select min(d),
                from
                    unnest(
                        [
                            sr.mid_year_withdrawal_date,
                            sr.summer_withdraw_date,
                            sr.not_enrolling_date
                        ]
                    ) as d
            ) as enrollment_end_date,

            case
                when sr.mid_year_withdrawal_date is not null
                then 'mid_year_withdrawal'
                when sr.summer_withdraw_date is not null
                then 'summer_withdraw'
                when sr.not_enrolling_date is not null
                then 'not_enrolling'
            end as withdrawal_reason,
        from contacts as c
        left join
            status_report_latest as sr
            on c.finalsite_enrollment_id = sr.finalsite_enrollment_id
    ),

    joined as (
        select
            finalsite_enrollment_id,
            finalsite_status,
            enrollment_type,
            school_year_start,
            grade_canonical_name,
            promotion_status,
            assigned_school,
            enrollment_start_date,
            enrollment_end_date,
            withdrawal_reason,

            (
                enrollment_start_date is not null and enrollment_end_date is not null
            ) as is_transfer_out,
        from dated
    )

select
    finalsite_enrollment_id,
    finalsite_status,
    enrollment_type,
    school_year_start,
    grade_canonical_name,
    promotion_status,
    assigned_school,
    enrollment_start_date,

    if(is_transfer_out, enrollment_end_date, cast(null as date)) as enrollment_end_date,

    if(is_transfer_out, withdrawal_reason, cast(null as string)) as withdrawal_reason,

    case
        when is_transfer_out
        then 'transfer_out'
        when enrollment_type = 'returning'
        then 're_enroll'
        else 'create'
    end as lifecycle_action,
from joined
where
    finalsite_status
    in ('accepted', 'enrollment_in_progress', 'assigned_school', 'enrolled', 'retained')
    or is_transfer_out
