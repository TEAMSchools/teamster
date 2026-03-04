with
    status_report as (
        select
            _dagster_partition_key,
            finalsite_enrollment_id,
            last_name,
            first_name,
            enrollment_type,
            active_school_year,
            self_contained,
            assigned_school,
            application_grade,
            gender,

            cast(powerschool_student_number as int) as powerschool_student_number,

            cast(birthdate as date) as birthdate,

            cast(inquiry_date as timestamp) as inquiry_timestamp,
            cast(inquiry_completed_date as timestamp) as inquiry_completed_timestamp,
            cast(inactive_inquiry_date as timestamp) as inactive_inquiry_timestamp,
            cast(applicant_date as timestamp) as applicant_timestamp,
            cast(
                application_withdrawn_date as timestamp
            ) as application_withdrawn_timestamp,
            cast(deferred_date as timestamp) as deferred_timestamp,
            cast(
                application_complete_date as timestamp
            ) as application_complete_timestamp,
            cast(review_in_progress_date as timestamp) as review_in_progress_timestamp,
            cast(waitlisted_date as timestamp) as waitlisted_timestamp,
            cast(denied_date as timestamp) as denied_timestamp,
            cast(ready_for_lottery_date as timestamp) as ready_for_lottery_timestamp,
            cast(accepted_date as timestamp) as accepted_timestamp,
            cast(did_not_enroll_date as timestamp) as did_not_enroll_timestamp,
            cast(assigned_school_date as timestamp) as assigned_school_timestamp,
            cast(
                campus_transfer_requested_date as timestamp
            ) as campus_transfer_requested_timestamp,
            cast(parent_declined_date as timestamp) as parent_declined_timestamp,
            cast(
                enrollment_in_progress_date as timestamp
            ) as enrollment_in_progress_timestamp,
            cast(academic_hold_date as timestamp) as academic_hold_timestamp,
            cast(financial_hold_date as timestamp) as financial_hold_timestamp,
            cast(not_enrolling_date as timestamp) as not_enrolling_timestamp,
            cast(enrolled_date as timestamp) as enrolled_timestamp,
            cast(
                mid_year_withdrawal_date as timestamp
            ) as mid_year_withdrawal_timestamp,
            cast(never_attended_date as timestamp) as never_attended_timestamp,
            cast(retained_date as timestamp) as retained_timestamp,
            cast(summer_withdraw_date as timestamp) as summer_withdraw_timestamp,

            cast(left(active_school_year, 4) as int) as active_school_year_int,
        from {{ source("finalsite", "status_report") }}
        where powerschool_student_number is null or powerschool_student_number != 'test'
    )

select
    *,

    date(inquiry_timestamp, '{{ var("local_timezone") }}') as inquiry_date,
    date(
        inquiry_completed_timestamp, '{{ var("local_timezone") }}'
    ) as inquiry_completed_date,
    date(
        inactive_inquiry_timestamp, '{{ var("local_timezone") }}'
    ) as inactive_inquiry_date,
    date(applicant_timestamp, '{{ var("local_timezone") }}') as applicant_date,
    date(
        application_withdrawn_timestamp, '{{ var("local_timezone") }}'
    ) as application_withdrawn_date,
    date(deferred_timestamp, '{{ var("local_timezone") }}') as deferred_date,
    date(
        application_complete_timestamp, '{{ var("local_timezone") }}'
    ) as application_complete_date,
    date(
        review_in_progress_timestamp, '{{ var("local_timezone") }}'
    ) as review_in_progress_date,
    date(waitlisted_timestamp, '{{ var("local_timezone") }}') as waitlisted_date,
    date(denied_timestamp, '{{ var("local_timezone") }}') as denied_date,
    date(
        ready_for_lottery_timestamp, '{{ var("local_timezone") }}'
    ) as ready_for_lottery_date,
    date(accepted_timestamp, '{{ var("local_timezone") }}') as accepted_date,
    date(
        did_not_enroll_timestamp, '{{ var("local_timezone") }}'
    ) as did_not_enroll_date,
    date(
        assigned_school_timestamp, '{{ var("local_timezone") }}'
    ) as assigned_school_date,
    date(
        campus_transfer_requested_timestamp, '{{ var("local_timezone") }}'
    ) as campus_transfer_requested_date,
    date(
        parent_declined_timestamp, '{{ var("local_timezone") }}'
    ) as parent_declined_date,
    date(
        enrollment_in_progress_timestamp, '{{ var("local_timezone") }}'
    ) as enrollment_in_progress_date,
    date(academic_hold_timestamp, '{{ var("local_timezone") }}') as academic_hold_date,
    date(
        financial_hold_timestamp, '{{ var("local_timezone") }}'
    ) as financial_hold_date,
    date(not_enrolling_timestamp, '{{ var("local_timezone") }}') as not_enrolling_date,
    date(enrolled_timestamp, '{{ var("local_timezone") }}') as enrolled_date,
    date(
        mid_year_withdrawal_timestamp, '{{ var("local_timezone") }}'
    ) as mid_year_withdrawal_date,
    date(
        never_attended_timestamp, '{{ var("local_timezone") }}'
    ) as never_attended_date,
    date(retained_timestamp, '{{ var("local_timezone") }}') as retained_date,
    date(
        summer_withdraw_timestamp, '{{ var("local_timezone") }}'
    ) as summer_withdraw_date,
from status_report
