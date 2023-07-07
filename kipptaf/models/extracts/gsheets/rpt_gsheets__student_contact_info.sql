{{ config(enabled=False) }}

select
    student_number,
    if(region = 'Miami', fleid, newark_enrollment_number) as newark_enrollment_number,
    state_studentnumber,
    lastfirst,
    schoolid,
    school_name,
    if(grade_level = 0, 'K', safe_cast(grade_level as string)) as grade_level,
    team,
    advisor_name,
    entrydate,
    boy_status,
    dob,
    gender,
    lunchstatus,
    case
        lunch_app_status
        when null
        then 'N'
        when 'No Application'
        then 'N'
        when lunch_app_status like 'Prior%'
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
    student_web_id + '.fam' as family_web_id,
    student_web_password as family_web_password,
    media_release,
    region,
    iep_status,
    lep_status,
    c_504_status,
    is_homeless,
    infosnap_opt_in,
    city,
    is_pathways as is_selfcontained,
    infosnap_id,
    rides_staff,
from {{ ref("base_powerschool__student_enrollments") }}
where enroll_status in (0, -1) and rn_all = 1
