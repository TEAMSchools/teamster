with
    pivot_source as (
        select incident_id, `value`, field_name,
        from {{ ref("stg_deanslist__incidents__custom_fields") }}
    )

select *
from
    pivot_source pivot (
        max(`value`) for field_name in (
            '1. Specific behavior/incident that prompted referral:'
            as `specific_behavior_incident_that_prompted_referral`,
            '2. Primary Area of Concern:' as `primary_area_of_concern`,
            '3. Level of Concern:' as `level_of_concern`,
            'Approver Name' as `approver_name`,
            'Behavior Category' as `behavior_category`,
            'Board Approval Date' as `board_approval_date`,
            'Board reconsideration date(s)' as `board_reconsideration_dates`,
            'Board Resolution Affirmation Date' as `board_resolution_affirmation_date`,
            'DCF notes/follow-up' as `dcf_notes_follow_up`,
            'DCF officer name' as `dcf_officer_name`,
            'Doctor Approval' as `doctor_approval`,
            'FedEx tracking # for determination' as `fedex_tracking_for_determination`,
            'FedEx tracking # for notice' as `fedex_tracking_for_notice`,
            'Final Approval' as `final_approval`,
            'HI end date' as `hi_end_date`,
            'HI start date' as `hi_start_date`,
            'Hourly Rate' as `hourly_rate`,
            'Hours per Week' as `hours_per_week`,
            'Initial Trigger (antecedent)' as `initial_trigger_antecedent`,
            'Instructor Name' as `instructor_name`,
            'Instructor Source' as `instructor_source`,
            'Intervention' as `intervention`,
            'Logical Redirection' as `logical_redirection`,
            'MDR Date (if IEP or 504)' as `mdr_date_if_iep_or_504`,
            'NJ State Reporting' as `nj_state_reporting`,
            'Non-student witnesses to restraint'
            as `non_student_witnesses_to_restraint`,
            'Others Involved' as `others_involved`,
            'Parent Contacted?' as `parent_contacted`,
            'Perceived Motivation' as `perceived_motivation`,
            "Reporter's ID number" as `reporters_id_number`,
            'Restraint Duration' as `restraint_duration`,
            'Restraint notes' as `restraint_notes`,
            'Restraint Type' as `restraint_type`,
            'Restraint Used' as `restraint_used`,
            'SSDS Incident ID' as `ssds_incident_id`,
            'Staff involved in restraint' as `staff_involved_in_restraint`,
            'Suspension logged?' as `suspension_logged`,
            'Teacher Response' as `teacher_response`
        )
    )
