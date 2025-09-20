with
    transcript_data as (
        select
            student,
            cumulative_credits_earned,
            credits_required_for_graduation,
            gpa,

            row_number() over (
                partition by student order by transcript_date desc
            ) as rn_transcript,
        from {{ ref("stg_kippadb__gpa") }}
    ),

    rem_subject as (
        select
            contact,
            `date`,
            `subject`,

            cast(concat('20', right(left(`subject`, 8), 2)) as int) as fiscal_year,

            row_number() over (partition by contact order by `date` desc) as rn_note,
        from {{ ref("stg_kippadb__contact_note") }}
        where `subject` like 'REM FY%'
    ),

    rem_handoff as (
        select
            contact,
            `date` as rem_handoff_date,
            `subject`,

            row_number() over (partition by contact order by `date` desc) as rn_note,
        from {{ ref("stg_kippadb__contact_note") }}
        where `subject` like 'REM Handoff'
    )

select
    r.lastfirst as student_name,
    r.contact_id,
    r.ktc_cohort,
    r.contact_owner_name,
    r.contact_college_match_display_gpa,
    r.contact_last_outreach as last_outreach_date,
    r.contact_last_successful_contact as last_successful_contact_date,
    r.contact_last_successful_advisor_contact as last_successful_advisor_contact_date,
    r.contact_latest_fafsa_date as latest_fafsa_date,

    ei.cur_status as `status`,
    ei.cur_actual_end_date as actual_end_date,
    ei.cur_credits_required_for_graduation as of_credits_required_for_graduation,
    ei.ugrad_pursuing_degree_type as college_degree_type,
    ei.cte_pursuing_degree_type as cte_degree_type,

    gpa.cumulative_credits_earned,
    gpa.credits_required_for_graduation,

    format_datetime('%Y-%m-%d', e.last_modified_date) as last_modified_date,

    (gpa.cumulative_credits_earned / gpa.credits_required_for_graduation)
    * 100 as degree_percentage_completed,

    rs.subject as rem_status,

    if(
        date_diff(
            current_date('{{ var("local_timezone") }}'),
            r.contact_last_successful_contact,
            day
        )
        > 30,
        'Successful Contact > 30 days',
        'Successful Contact within 30'
    ) as successful_contact_status,

    if(
        date_diff(
            current_date('{{ var("local_timezone") }}'), r.contact_last_outreach, day
        )
        > 30,
        'Last Outreach > 30 days',
        'Last Outreach within 30'
    ) as last_outreach_status,

    date_diff(
        rh.rem_handoff_date, r.contact_last_successful_contact, day
    ) as rem_contact_days_since_handoff,

    r.contact_kipp_hs_graduate as is_kipp_hs_grad,
    r.contact_expected_college_graduation as expected_college_graduation,

    if(r.contact_advising_provider = 'KIPP NYC', true, false) as is_collab,

    rs.date as most_recent_rem_status,

    rh.rem_handoff_date,

    case
        when ei.cur_status = 'Attending' and rs.subject like 'REM%FY%Q% Enrolled'
        then 'REM Enrolled'
        when ei.cur_status = 'Graduated' and rs.subject like 'REM%FY%Q% Enrolled'
        then 'REM Graduated'
        when ei.cur_status = 'Withdrawn' and rs.subject like 'REM%FY%Q% Enrolled'
        then 'REM Withdrawn'
        when ei.cur_status = 'Matriculated' and rs.subject like 'REM%FY%Q% Enrolled'
        then 'REM Matriculated'
    end as rem_enrollment_status,

    case
        when r.contact_college_match_display_gpa >= 3.50
        then '3.50+'
        when r.contact_college_match_display_gpa >= 3.00
        then '3.00-3.49'
        when r.contact_college_match_display_gpa >= 2.50
        then '2.50-2.99'
        when r.contact_college_match_display_gpa >= 2.00
        then '2.00-2.50'
        when r.contact_college_match_display_gpa < 2.00
        then '<2.00'
    end as hs_gpa_bands,

    case
        when ei.ba_status = 'Graduated'
        then 'BA graduate'
        when ei.aa_status = 'Graduated'
        then 'AA graduate'
        when ei.cte_status = 'Graduated'
        then 'CTE graduate'
        when ei.ugrad_enrollment_id is null and ei.cte_enrollment_id is null
        then 'Never enrolled'
        when
            ei.ba_status = 'Attending'
            or ei.aa_status = 'Attending'
            or ei.cte_status = 'Attending'
        then 'Attending'
    end as is_graduated,

    r.first_name,
    r.last_name,
    r.contact_home_phone,
    r.contact_mobile_phone,
    r.contact_email,
    r.contact_secondary_email,

    gpa.gpa,

    rs.fiscal_year,

    r.contact_middle_school_attended,
    r.contact_postsecondary_status,

    if(r.contact_most_recent_iep_date is not null, 'Has IEP', 'No IEP') as iep_status,

    if(
        ei.ecc_pursuing_degree_type
        in ("Associate's (2 year)", "Bachelor's (4-year)", 'Certificate'),
        true,
        false
    ) as is_enrolled_bool,

    r.contact_most_recent_college_enrollment_name as most_recent_college_enrollment,
    r.contact_most_recent_college_enrollment_status
    as most_recent_college_enrollment_status,
    r.contact_currently_enrolled_school as currently_enrolled_school,

    r.lastfirst || ' - ' || r.contact_id as student_name_id_hash,
from {{ ref("int_kippadb__roster") }} as r
left join {{ ref("int_kippadb__enrollment_pivot") }} as ei on r.contact_id = ei.student
left join {{ ref("stg_kippadb__enrollment") }} as e on ei.cur_enrollment_id = e.id
left join rem_subject as rs on r.contact_id = rs.contact and rs.rn_note = 1
left join rem_handoff as rh on r.contact_id = rh.contact and rh.rn_note = 1
left join transcript_data as gpa on r.contact_id = gpa.student and gpa.rn_transcript = 1
where r.contact_has_hs_graduated_enrollment = 'HS Graduate'
