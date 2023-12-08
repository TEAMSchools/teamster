with
    enrollment_status as (
        select
            ei.student,
            ei.name,
            ei.actual_end_date,
            ei.last_modified_date,
            ei.status,
            ei.of_credits_required_for_graduation,
            row_number() over (
                partition by ei.student order by ei.start_date desc
            ) as rn_enrollment
        from {{ ref("stg_kippadb__enrollment") }} as ei
        where ei.status = 'Withdrawn'
    ),
    transcript_data as (
        select
            gpa.student,
            gpa.cumulative_credits_earned,
            gpa.credits_required_for_graduation,
            row_number() over (
                partition by gpa.student order by gpa.transcript_date desc
            ) as rn_transcript
        from {{ ref("stg_kippadb__gpa") }} as gpa
    )
select
    kt.student_name,
    kt.contact_id,
    kt.ktc_cohort,
    ei.status,
    ei.actual_end_date,
    format_datetime('%Y-%m-%d', ei.last_modified_date) as last_modified_date,
    ei.of_credits_required_for_graduation,
    kt.last_outreach_date,
    kt.last_successful_contact_date,
    kt.last_successful_advisor_contact_date,
    kt.latest_fafsa_date,
    gpa.cumulative_credits_earned,
    gpa.credits_required_for_graduation,
    (gpa.cumulative_credits_earned / gpa.credits_required_for_graduation)
    * 100 as degree_percentage_completed,
    -- COALESCE(kt.spr_cumulative_credits_earned, kt.fall_cumulative_credits_earned)
    -- AS cumulative_credits_earned,
    -- kt.cur_credits_required_for_graduation,
    case
        when cn.subject like 'REM%FY%Q%' then cn.subject else 'other subject'
    end as rem_status,
    case
        when
            date_diff(
                current_date('America/New_York'), kt.last_successful_contact_date, day
            )
            > 30
        then 'Succesful Contact > 30 days'
        else 'Successful Contact within 30'
    end as successful_contact_status,
    case
        when
            date_diff(current_date('America/New_York'), kt.last_outreach_date, day) > 30
        then 'Last Outreach > 30 days'
        else 'Last Outreach within 30'
    end as last_outreach_status
from `teamster-332318.kipptaf_tableau.rpt_tableau__kfwd_dashboard` as kt
left join enrollment_status as ei on kt.contact_id = ei.student and ei.rn_enrollment = 1
left join
    `teamster-332318.kipptaf_tableau.rpt_tableau__kfwd_contact_notes` as cn
    on kt.contact_id = cn.sf_contact_id
    and cn.subject like 'REM%'
left join
    transcript_data as gpa on gpa.student = kt.contact_id and gpa.rn_transcript = 1
where
    kt.academic_year = {{ var("current_academic_year") }}
    and kt.current_kipp_student = 'KIPP HS Graduate'
