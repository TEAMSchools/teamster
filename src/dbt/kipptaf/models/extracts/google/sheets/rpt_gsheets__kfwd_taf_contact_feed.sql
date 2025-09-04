select
    r.student_number as ps_student_number,
    r.contact_id as sf_contact_id,
    r.lastfirst as student_name,
    r.ktc_cohort as sf_cohort,
    r.contact_birthdate as dob,
    r.exit_school_name,
    r.exit_date,
    r.exit_grade_level,
    r.current_grade_level_projection,
    r.contact_expected_hs_graduation as expected_hs_grad_date,
    r.contact_owner_name,
    r.contact_home_phone as sf_home_phone,
    r.contact_mobile_phone as sf_mobile_phone,
    r.contact_other_phone as sf_other_phone,
    r.contact_email as sf_primary_email,
    r.contact_secondary_email as sf_secondary_email,
    r.contact_mailing_address as sf_mailing_address,

    e.cur_pursuing_degree_type,
    e.cur_account_type,
    e.cur_status,
    e.cur_school_name,
    e.cur_start_date,
    e.cur_actual_end_date,
    e.cur_anticipated_graduation,

    r.state_studentnumber,
    r.powerschool_contact_1_name as ps_contact_1_name,
    r.powerschool_contact_1_relationship as ps_contact_1_relationship,
    r.powerschool_contact_1_email_current as ps_contact_1_email_current,
    r.powerschool_contact_1_phone_daytime as ps_contact_1_phone_daytime,
    r.powerschool_contact_1_phone_home as ps_contact_1_phone_home,
    r.powerschool_contact_1_phone_mobile as ps_contact_1_phone_mobile,
    r.powerschool_contact_1_phone_primary as ps_contact_1_phone_primary,
    r.powerschool_contact_1_phone_work as ps_contact_1_phone_work,
    r.powerschool_contact_2_name as ps_contact_2_name,
    r.powerschool_contact_2_relationship as ps_contact_2_relationship,
    r.powerschool_contact_2_email_current as ps_contact_2_email_current,
    r.powerschool_contact_2_phone_daytime as ps_contact_2_phone_daytime,
    r.powerschool_contact_2_phone_home as ps_contact_2_phone_home,
    r.powerschool_contact_2_phone_mobile as ps_contact_2_phone_mobile,
    r.powerschool_contact_2_phone_primary as ps_contact_2_phone_primary,
    r.powerschool_contact_2_phone_work as ps_contact_2_phone_work,
    r.powerschool_emergency_contact_1_name as ps_emergency_contact_1_name,
    r.powerschool_emergency_contact_1_relationship
    as ps_emergency_contact_1_relationship,
    r.powerschool_emergency_contact_1_phone_daytime
    as ps_emergency_contact_1_phone_daytime,
    r.powerschool_emergency_contact_1_phone_home as ps_emergency_contact_1_phone_home,
    r.powerschool_emergency_contact_1_phone_mobile
    as ps_emergency_contact_1_phone_mobile,
    r.powerschool_emergency_contact_1_phone_primary
    as ps_emergency_contact_1_phone_primary,
    r.powerschool_emergency_contact_2_name as ps_emergency_contact_2_name,
    r.powerschool_emergency_contact_2_relationship
    as ps_emergency_contact_2_relationship,
    r.powerschool_emergency_contact_2_phone_daytime
    as ps_emergency_contact_2_phone_daytime,
    r.powerschool_emergency_contact_2_phone_home as ps_emergency_contact_2_phone_home,
    r.powerschool_emergency_contact_2_phone_mobile
    as ps_emergency_contact_2_phone_mobile,
    r.powerschool_emergency_contact_2_phone_primary
    as ps_emergency_contact_2_phone_primary,
    r.powerschool_emergency_contact_3_name as ps_emergency_contact_3_name,
    r.powerschool_emergency_contact_3_relationship
    as ps_emergency_contact_3_relationship,
    r.powerschool_emergency_contact_3_phone_daytime
    as ps_emergency_contact_3_phone_daytime,
    r.powerschool_emergency_contact_3_phone_home as ps_emergency_contact_3_phone_home,
    r.powerschool_emergency_contact_3_phone_mobile
    as ps_emergency_contact_3_phone_mobile,
    r.powerschool_emergency_contact_3_phone_primary
    as ps_emergency_contact_3_phone_primary,
    r.region,
    r.ps_home_address,
from {{ ref("int_kippadb__roster") }} as r
left join {{ ref("int_kippadb__enrollment_pivot") }} as e on r.contact_id = e.student
where r.ktc_status like 'TAF%'
