with
    unpivot_data as (
        select
            active_school_year,
            region,
            assigned_school,
            finalsite_student_id,
            powerschool_student_number,
            first_name,
            last_name,
            grade,
            self_contained,

            fs_status_field,
            safe_cast(status_start_timestamp as date) as status_start_date,

            initcap(
                replace(replace(fs_status_field, '_', ' '), ' Date', '')
            ) as detailed_status,

        from
            -- trunk-ignore(sqlfluff/LT01)
            {{ ref("stg_finalsite__status_report_wide") }} unpivot include nulls(
                status_start_timestamp for fs_status_field in (
                    inquiry_date,
                    inquiry_completed_date,
                    inactive_inquiry_date,
                    applicant_date,
                    application_withdrawn_date,
                    deferred_date,
                    application_complete_date,
                    review_in_progress_date,
                    waitlisted_date,
                    denied_date,
                    accepted_date,
                    did_not_enroll_date,
                    assigned_school_date,
                    campus_transfer_requested_date,
                    parent_declined_date,
                    enrollment_in_progress_date,
                    academic_hold_date,
                    financial_hold_date,
                    not_enrolling_date,
                    enrolled_date,
                    mid_year_withdrawal_date,
                    never_attended_date,
                    retained_date,
                    summer_withdraw_date
                )
            )
    ),

    status_order_field as (
        select
            u.*,

            'KTAF' as org,

            coalesce(x.powerschool_school_id, 0) as schoolid,
            coalesce(x.abbreviation, 'No School Assigned') as school,

            case
                u.fs_status_field
                when 'inquiry_date'
                then 1
                when 'inquiry_completed_date'
                then 2
                when 'inactive_inquiry_date'
                then 3
                when 'applicant_date'
                then 4
                when 'application_withdrawn_date'
                then 5
                when 'deferred_date'
                then 6
                when 'application_complete_date'
                then 7
                when 'review_in_progress_date'
                then 8
                when 'waitlisted_date'
                then 9
                when 'denied_date'
                then 10
                when 'accepted_date'
                then 11
                when 'assigned_school_date'
                then 12
                when 'did_not_enroll_date'
                then 13
                when 'campus_transfer_requested_date'
                then 14
                when 'parent_declined_date'
                then 15
                when 'enrollment_in_progress_date'
                then 16
                when 'academic_hold_date'
                then 17
                when 'financial_hold_date'
                then 18
                when 'not_enrolling_date'
                then 19
                when 'enrolled_date'
                then 20
                when 'mid_year_withdrawal_date'
                then 21
                when 'never_attended_date'
                then 22
                when 'retained_date'
                then 23
                when 'summer_withdraw_date'
                then 24
            end as status_order,

        from unpivot_data as u
        left join
            {{ ref("stg_google_sheets__people__location_crosswalk") }} as x
            on u.assigned_school = x.name
    ),

    end_date as (
        select
            *,

            lead(
                status_start_date,
                1,
                current_date('{{ var("local_timezone") }}')
            ) over (
                partition by finalsite_student_id, active_school_year
                order by status_start_date asc, status_order asc
            ) as status_end_date,

        from status_order_field
    )

select
    *,

    if(
        status_end_date = status_start_date,
        1,
        date_diff(status_end_date, status_start_date, day)
    ) as days_in_status,

from end_date
