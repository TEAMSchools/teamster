select  -- noqa: disable=ST06
    student_number,
    if(region = 'Miami', fleid, newark_enrollment_number) as newark_enrollment_number,
    state_studentnumber,
    lastfirst,
    schoolid,
    school_name,
    if(grade_level = 0, 'K', safe_cast(grade_level as string)) as grade_level,
    advisory_name as team,
    advisor_lastfirst as advisor_name,
    entrydate,
    case
        when grade_level = 99
        then 'Graduated'
        when year_in_network = 1
        then 'New'
        when grade_level_prev is null
        then 'New'
        when grade_level_prev < grade_level
        then 'Promoted'
        when grade_level_prev = grade_level
        then 'Retained'
        when grade_level_prev > grade_level
        then 'Demoted'
    end as boy_status,
    dob,
    gender,
    lunch_status as lunchstatus,
    case
        when lunch_application_status is null
        then 'N'
        when lunch_application_status = 'No Application'
        then 'N'
        when lunch_application_status like 'Prior%'
        then 'N'
        else 'Y'
    end as lunch_app_status,
    lunch_balance,
    home_phone,
    contact_1_phone_primary as mother_cell,
    contact_2_phone_primary as father_cell,
    contact_1_name as mother,
    contact_2_name as father,
    concat(pickup_1_name, ' | ', pickup_1_phone_mobile) as release_1,
    concat(pickup_2_name, ' | ', pickup_2_phone_mobile) as release_2,
    concat(pickup_3_name, ' | ', pickup_3_phone_mobile) as release_3,
    null as release_4,
    null as release_5,
    coalesce(contact_1_email_current, contact_2_email_current) as guardianemail,
    concat(street, ', ', city, ', ', `state`, ' ', zip) as `address`,
    first_name,
    last_name,
    student_web_id,
    student_web_password,
    student_web_id || '.fam' as family_web_id,
    student_web_password as family_web_password,
    media_release,
    region,
    spedlep as iep_status,
    lep_status,
    is_504 as c_504_status,
    is_homeless,
    infosnap_opt_in,
    city,
    is_self_contained as is_selfcontained,
    infosnap_id,
    rides_staff,
from {{ ref("base_powerschool__student_enrollments") }}
where enroll_status in (0, -1) and rn_all = 1
