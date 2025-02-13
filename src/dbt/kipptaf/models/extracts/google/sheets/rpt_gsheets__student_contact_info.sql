-- trunk-ignore(sqlfluff/ST06)
select
    co.student_number,

    if(
        co.region = 'Miami', co.fleid, co.newark_enrollment_number
    ) as newark_enrollment_number,

    co.state_studentnumber,
    co.lastfirst,
    co.schoolid,
    co.school_name,

    if(co.grade_level = 0, 'K', safe_cast(co.grade_level as string)) as grade_level,

    co.advisory_name as team,
    co.advisor_lastfirst as advisor_name,
    co.entrydate,
    co.boy_status,
    co.dob,
    co.gender,
    co.lunch_status as lunchstatus,

    case
        when co.lunch_application_status is null
        then 'N'
        when co.lunch_application_status = 'No Application'
        then 'N'
        when co.lunch_application_status like 'Prior%'
        then 'N'
        else 'Y'
    end as lunch_app_status,

    co.lunch_balance,
    co.home_phone,
    co.contact_1_phone_primary as mother_cell,
    co.contact_2_phone_primary as father_cell,
    co.contact_1_name as mother,
    co.contact_2_name as father,

    concat(co.pickup_1_name, ' | ', co.pickup_1_phone_mobile) as release_1,
    concat(co.pickup_2_name, ' | ', co.pickup_2_phone_mobile) as release_2,
    concat(co.pickup_3_name, ' | ', co.pickup_3_phone_mobile) as release_3,

    null as release_4,
    null as release_5,

    coalesce(co.contact_1_email_current, co.contact_2_email_current) as guardianemail,
    concat(co.street, ', ', co.city, ', ', co.`state`, ' ', co.zip) as `address`,

    co.first_name,
    co.last_name,
    co.student_web_id,
    co.student_web_password,

    co.student_web_id || '.fam' as family_web_id,

    co.student_web_password as family_web_password,
    co.media_release,
    co.region,
    co.spedlep as iep_status,
    co.lep_status,
    co.is_504 as c_504_status,
    co.is_homeless,
    co.infosnap_opt_in,
    co.city,
    co.is_self_contained as is_selfcontained,
    co.infosnap_id,
    co.rides_staff,
    co.gifted_and_talented,

    r.contact_id as salesforce_contact_id,
from {{ ref("base_powerschool__student_enrollments") }} as co
left join {{ ref("int_kippadb__roster") }} as r on co.student_number = r.student_number
where enroll_status in (0, -1) and rn_all = 1
