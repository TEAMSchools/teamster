with
    transcript_data as (
        select
            student,
            cumulative_credits_earned,
            credits_required_for_graduation,
            row_number() over (
                partition by student order by transcript_date desc
            ) as rn_transcript,
        from {{ ref("stg_kippadb__gpa") }}
    ),

    rem_subject as (
        select
            contact,
            `date`,
            subject,
            row_number() over (partition by contact order by date desc) as rn_note,
        from {{ ref("stg_kippadb__contact_note") }}
        where subject like 'REM FY%'
    )

select  -- noqa: ST06
    r.lastfirst as student_name,
    r.contact_id,
    r.ktc_cohort,
    r.contact_owner_name,

    c.contact_last_outreach as last_outreach_date,
    c.contact_last_successful_contact as last_successful_contact_date,
    c.contact_last_successful_advisor_contact as last_successful_advisor_contact_date,
    c.contact_latest_fafsa_date as latest_fafsa_date,

    ei.cur_status as status,
    ei.cur_actual_end_date as actual_end_date,
    ei.cur_credits_required_for_graduation as of_credits_required_for_graduation,

    gpa.cumulative_credits_earned,
    gpa.credits_required_for_graduation,

    format_datetime('%Y-%m-%d', e.last_modified_date) as last_modified_date,

    (gpa.cumulative_credits_earned / gpa.credits_required_for_graduation)
    * 100 as degree_percentage_completed,
    rs.subject as rem_status,
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

    r.contact_kipp_hs_graduate as is_kipp_hs_grad,
    r.contact_expected_college_graduation as expected_college_graduation,
    if(r.contact_advising_provider = 'KIPP NYC', true, false) as is_collab,
    rs.date as most_recent_rem_status,

    case
        when ei.cur_status = 'Attending' and rs.subject like 'REM%FY%Q% Enrolled'
        then 'REM Enrolled'
        when ei.cur_status = 'Graduated' and rs.subject like 'REM%FY%Q% Enrolled'
        then 'REM Graduated'
        when ei.cur_status = 'Withdrawn' and rs.subject like 'REM%FY%Q% Enrolled'
        then 'REM Withdrawn'
    end as rem_enrollment_status,
from {{ ref("int_kippadb__roster") }} as r
left join {{ ref("base_kippadb__contact") }} as c on r.contact_id = c.contact_id
left join {{ ref("int_kippadb__enrollment_pivot") }} as ei on r.contact_id = ei.student
left join {{ ref("stg_kippadb__enrollment") }} as e on ei.cur_enrollment_id = e.id
left join rem_subject as rs on rs.contact = r.contact_id and rs.rn_note = 1
left join transcript_data as gpa on gpa.student = r.contact_id and gpa.rn_transcript = 1
where r.contact_has_hs_graduated_enrollment = 'HS Graduate'
