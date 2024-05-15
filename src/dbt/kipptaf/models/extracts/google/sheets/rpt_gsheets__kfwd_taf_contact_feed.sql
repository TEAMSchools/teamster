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

    co.contact_1_name as ps_contact_1_name,
    co.contact_1_relationship as ps_contact_1_relationship,
    co.contact_1_email_current as ps_contact_1_email_current,
    co.contact_1_phone_daytime as ps_contact_1_phone_daytime,
    co.contact_1_phone_home as ps_contact_1_phone_home,
    co.contact_1_phone_mobile as ps_contact_1_phone_mobile,
    co.contact_1_phone_primary as ps_contact_1_phone_primary,
    co.contact_1_phone_work as ps_contact_1_phone_work,
    co.contact_2_name as ps_contact_2_name,
    co.contact_2_relationship as ps_contact_2_relationship,
    co.contact_2_email_current as ps_contact_2_email_current,
    co.contact_2_phone_daytime as ps_contact_2_phone_daytime,
    co.contact_2_phone_home as ps_contact_2_phone_home,
    co.contact_2_phone_mobile as ps_contact_2_phone_mobile,
    co.contact_2_phone_primary as ps_contact_2_phone_primary,
    co.contact_2_phone_work as ps_contact_2_phone_work,
    co.region,

    concat(co.street, ' ', co.city, ', ', co.state, ' ', co.zip) as ps_home_address,
from {{ ref("int_kippadb__roster") }} as r
left join {{ ref("int_kippadb__enrollment_pivot") }} as e on r.contact_id = e.student
left join
    {{ ref("base_powerschool__student_enrollments") }} as co
    on r.student_number = co.student_number
    and co.rn_undergrad = 1
    and co.grade_level != 99
where r.ktc_status like 'TAF%'
