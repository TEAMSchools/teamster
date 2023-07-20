with
    pivot_source as (
        select incident_id, `value`, field_name,
        from {{ ref("stg_deanslist__incidents__custom_fields") }}
    )

select *
from
    pivot_source pivot (
        max(`value`) for field_name in (
            'Approver Name' as `approver_name`,
            'Behavior Category' as `behavior_category`,
            'Board Approval Date' as `board_approval_date`,
            'Board reconsideration date(s)' as `board_reconsideration_dates`,
            'Board Resolution Affirmation Date' as `board_resolution_affirmation_date`,
            'Doctor Approval' as `doctor_approval`,
            'FedEx tracking # for determination' as `fedex_tracking_for_determination`,
            'FedEx tracking # for notice' as `fedex_tracking_for_notice`,
            'Final Approval' as `final_approval`,
            'HI end date' as `hi_end_date`,
            'HI start date' as `hi_start_date`,
            'Hourly Rate' as `hourly_rate`,
            'Hours per Week' as `hours_per_week`,
            'Instructor Name' as `instructor_name`,
            'Instructor Source' as `instructor_source`,
            'Logical Redirection' as `logical_redirection`,
            'MDR Date (if IEP or 504)' as `mdr_date_if_iep_or_504`,
            'NJ State Reporting' as `nj_state_reporting`,
            'Perceived Motivation' as `perceived_motivation`,
            'Restraint Duration' as `restraint_duration`,
            'Restraint Type' as `restraint_type`,
            'Restraint Used' as `restraint_used`,
            'SSDS Incident ID' as `ssds_incident_id`,
            'Teacher Response' as `teacher_response`
        )
    )
