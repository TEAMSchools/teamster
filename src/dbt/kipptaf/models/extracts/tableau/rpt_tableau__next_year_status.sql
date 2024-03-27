select
    co.student_number,
    co.state_studentnumber,
    co.lastfirst,
    co.enroll_status,
    co.cohort,
    co.academic_year,
    co.region,
    co.schoolid,
    co.school_name,
    co.grade_level,
    co.entrydate,
    co.exitdate,
    co.gender,
    co.dob,
    co.spedlep,
    co.is_retained_ever,
    co.is_retained_year,
    co.year_in_school,
    co.home_phone,
    co.contact_1_phone_mobile,
    co.contact_2_phone_mobile,
    co.contact_1_email_current,
    co.next_school,
    co.boy_status,

    coalesce(co.sched_nextyeargrade, 0) as sched_nextyeargrade,

    concat('+1', replace(co.home_phone, '-', '')) as tel_home_phone,
    concat('+1', replace(co.contact_1_phone_mobile, '-', '')) as tel_mother_cell,
    concat('+1', replace(co.contact_2_phone_mobile, '-', '')) as tel_father_cell,
    concat(co.street, ', ', co.city, ', ', co.state, ' ', co.zip) as student_address,

    replace(
        concat(co.street, '+', co.city, '+', co.state, '+', co.zip), ' ', '+'
    ) as gmaps_address,
from {{ ref("base_powerschool__student_enrollments") }} as co
where co.rn_undergrad = 1 and co.enroll_status in (0, -1)
