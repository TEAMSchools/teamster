with
    enrollment_status as (
        select
            student,
            name,
            actual_end_date,
            last_modified_date,
            status,
            of_credits_required_for_graduation,
            row_number() over (
                partition by ei.student order by ei.start_date desc
            ) as rn_enrollment
        from {{ ref("stg_kippadb__enrollment") }} as ei
        where status = 'Withdrawn'
    ),

    transcript_data as (
        select
            student,
            cumulative_credits_earned,
            credits_required_for_graduation,
            row_number() over (
                partition by student order by transcript_date desc
            ) as rn_transcript
        from {{ ref("stg_kippadb__gpa") }}
    )

select
    r.lastfirst as student_name,
    r.contact_id,
    r.ktc_cohort,

    c.contact_last_outreach as last_outreach_date,
    c.contact_last_successful_contact as last_successful_contact_date,
    c.contact_last_successful_advisor_contact as last_successful_advisor_contact_date,
    c.contact_latest_fafsa_date as latest_fafsa_date,

    ei.status,
    ei.actual_end_date,
    ei.of_credits_required_for_graduation,

    gpa.cumulative_credits_earned,
    gpa.credits_required_for_graduation,

    format_datetime('%Y-%m-%d', ei.last_modified_date) as last_modified_date,

    (gpa.cumulative_credits_earned / gpa.credits_required_for_graduation)
    * 100 as degree_percentage_completed,
    case
        when cn.subject like 'REM%FY%Q%' then cn.subject else 'other subject'
    end as rem_status,
    case
        when
            date_diff(
                current_date('America/New_York'), c.contact_last_successful_contact, day
            )
            > 30
        then 'Succesful Contact > 30 days'
        else 'Successful Contact within 30'
    end as successful_contact_status,
    case
        when
            date_diff(current_date('America/New_York'), c.contact_last_outreach, day)
            > 30
        then 'Last Outreach > 30 days'
        else 'Last Outreach within 30'
    end as last_outreach_status,
from {{ ref("int_kippadb__roster") }} as r
left join {{ ref("base_kippadb__contact") }} as c on r.contact_id = c.contact_id
left join enrollment_status as ei on r.contact_id = ei.student and ei.rn_enrollment = 1
left join
    {{ ref("stg_kippadb__contact_note") }} as cn
    on r.contact_id = cn.contact
    and cn.subject like 'REM%'
left join transcript_data as gpa on gpa.student = r.contact_id and gpa.rn_transcript = 1
where r.contact_current_kipp_student = 'KIPP HS Graduate'
