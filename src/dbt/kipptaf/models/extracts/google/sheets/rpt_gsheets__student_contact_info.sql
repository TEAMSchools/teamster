-- trunk-ignore(sqlfluff/ST06)
select
    student_number,

    if(region = 'Miami', fleid, newark_enrollment_number) as newark_enrollment_number,

    if(
        region = 'Miami', secondary_state_studentnumber, state_studentnumber
    ) as state_studentnumber,

    student_name as lastfirst,
    schoolid,
    school_name,

    if(grade_level = 0, 'K', safe_cast(grade_level as string)) as grade_level,

    advisory_name as team,
    advisor_lastfirst as advisor_name,
    entrydate,
    boy_status,
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

    -- The release columns hold the student's emergency contacts. They read the
    -- pickup_* slots until #4751; no model has emitted a pickup_* contact slot
    -- since the Finalsite cutover, so every release column was empty for every
    -- NJ student. array_to_string rather than concat: concat returns NULL if
    -- either argument is NULL, which would drop the contact's name entirely for
    -- the minority with no phone on file.
    array_to_string(
        [
            emergency_1_name,
            coalesce(emergency_1_phone_mobile, emergency_1_phone_primary)
        ],
        ' | '
    ) as release_1,
    array_to_string(
        [
            emergency_2_name,
            coalesce(emergency_2_phone_mobile, emergency_2_phone_primary)
        ],
        ' | '
    ) as release_2,
    array_to_string(
        [
            emergency_3_name,
            coalesce(emergency_3_phone_mobile, emergency_3_phone_primary)
        ],
        ' | '
    ) as release_3,
    array_to_string(
        [
            emergency_4_name,
            coalesce(emergency_4_phone_mobile, emergency_4_phone_primary)
        ],
        ' | '
    ) as release_4,

    null as release_5,

    coalesce(contact_1_email_current, contact_2_email_current) as guardianemail,
    concat(street, ', ', city, ', ', `state`, ' ', zip) as `address`,

    student_first_name as first_name,
    student_last_name as last_name,
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
    gifted_and_talented,
    salesforce_id as salesforce_contact_id,
    home_language,

    -- Prior-level history only. The upstream columns of the same name pick the
    -- most recent enrollment at each level INCLUDING the current one, so a
    -- current MS student's ms_attended is their own school. Blanking every
    -- level at or below the student's current level makes these read as "KIPP
    -- schools attended before this one". At-or-below rather than the matching
    -- level alone also suppresses a stray MS enrollment record carried by one
    -- Camden ES student.
    if(school_level = 'ES', null, es_attended) as es_attended,
    if(school_level in ('ES', 'MS'), null, ms_attended) as ms_attended,
from {{ ref("int_extracts__student_enrollments") }}
where enroll_status in (0, -1) and rn_all = 1
