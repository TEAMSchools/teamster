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
from {{ ref("int_kippadb__roster") }} as ktc
inner join {{ ref("stg_kippadb__contact_note") }} as cn on ktc.contact_id = cn.contact
