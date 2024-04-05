select
    co.student_number,
    co.state_studentnumber,
    co.lastfirst as student_name,
    co.grade_level as last_kipp_grade_level,
    co.region as last_kipp_region,
    co.school_abbreviation as last_kipp_school,
    co.advisor_lastfirst as last_kipp_advisor,
    co.exitdate as exit_date,
    co.exitcode as nj_exit_code,
    co.exit_code_ts as kipp_exit_code,
    co.exitcomment,
    co.contact_1_name,
    co.contact_1_relationship,
    co.contact_2_name,
    co.contact_2_relationship,

    ei.hs_account_name as salesforce_hs_name,

    if(
        r.contact_owner_name in ('KNJ Admin', 'Diane Adams', 'Amanda Gewirtz')
        or r.contact_owner_name is null,
        'None',
        r.contact_owner_name
    ) as kipp_forward_counselor,
    coalesce(
        co.contact_1_phone_primary,
        co.contact_1_phone_mobile,
        co.contact_1_phone_daytime,
        co.contact_1_phone_home,
        co.contact_1_phone_work
    ) as contact_1_phone,
    coalesce(
        co.contact_2_phone_primary,
        co.contact_2_phone_mobile,
        co.contact_2_phone_daytime,
        co.contact_2_phone_home,
        co.contact_2_phone_work
    ) as contact_2_phone,
    concat(co.academic_year, '-', co.academic_year + 1) as last_kipp_academic_year,
from {{ ref("base_powerschool__student_enrollments") }} as co
left join {{ ref("int_kippadb__roster") }} as r on co.student_number = r.student_number
left join {{ ref("int_kippadb__enrollment_pivot") }} as ei on r.contact_id = ei.student
where
    co.rn_undergrad = 1
    and co.rn_year = 1
    and co.grade_level between 8 and 12
    and co.enroll_status = 2
    and co.region != 'Miami'
    and co.cohort >= {{ var("current_academic_year") }} - 2
