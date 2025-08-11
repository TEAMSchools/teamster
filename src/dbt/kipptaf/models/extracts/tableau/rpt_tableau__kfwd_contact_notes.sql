with
    sw_referral as (
        select
            contact,
            academic_year,
            date,

            row_number() over (
                partition by contact, academic_year order by date desc
            ) as rn_referral,
        from {{ ref("stg_kippadb__contact_note") }}
        where subject in ('SW REM Referral', 'SW Teammate Referral', 'SW Self Referral')
    )

select
    ktc.contact_id as sf_contact_id,
    ktc.first_name,
    ktc.last_name,
    ktc.contact_current_kipp_student as current_kipp_student,
    ktc.contact_kipp_region_name as kipp_region_name,
    ktc.contact_college_match_display_gpa as college_match_display_gpa,
    ktc.contact_currently_enrolled_school as currently_enrolled_school,
    ktc.contact_latest_fafsa_date as latest_fafsa_date,
    ktc.contact_latest_state_financial_aid_app_date
    as latest_state_financial_aid_app_date,
    ktc.contact_last_successful_advisor_contact as last_successful_advisor_contact_date,
    ktc.contact_last_successful_contact as last_successful_contact_date,
    ktc.contact_last_outreach as last_outreach_date,
    ktc.contact_owner_name as counselor_name,

    cn.created_by_id,
    cn.subject,
    cn.date,
    cn.comments,
    cn.next_steps,
    cn.status,
    cn.type,
    cn.academic_year,

    sw.date as referral_date,

    if(cn.status = 'Successful' and cn.type = 'School Visit', 1, 0) as school_visit,
from {{ ref("int_kippadb__roster") }} as ktc
inner join {{ ref("stg_kippadb__contact_note") }} as cn on ktc.contact_id = cn.contact
left join
    sw_referral as sw
    on cn.contact = sw.contact
    and cn.academic_year = sw.academic_year
    and sw.rn_referral = 1
