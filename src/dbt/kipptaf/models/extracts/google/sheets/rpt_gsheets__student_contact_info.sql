with
    -- Band every enrollment by the GRADE the student was in, not by the school's
    -- school_level. An increasing number of schools are off-model (e.g. an
    -- ES-coded school serving grades 5-8), so school_level misfiles their
    -- enrollments -- it would report such a school as a student's elementary
    -- school while they attend it for middle school.
    grade_band_enrollments as (
        select
            _dbt_source_project,
            student_number,
            school_abbreviation,
            exitdate,

            case
                when grade_level between 0 and 4
                then 'ES'
                when grade_level between 5 and 8
                then 'MS'
                when grade_level between 9 and 12
                then 'HS'
            end as grade_band,
        from {{ ref("base_powerschool__student_enrollments") }}
    ),

    grade_band_ranked as (
        select
            _dbt_source_project,
            student_number,
            school_abbreviation,
            grade_band,

            row_number() over (
                partition by _dbt_source_project, student_number, grade_band
                order by exitdate desc, school_abbreviation asc
            ) as rn_grade_band,
        from grade_band_enrollments
        where grade_band is not null
    ),

    most_recent_school_by_grade_band as (
        select _dbt_source_project, student_number, school_abbreviation, grade_band,
        from grade_band_ranked
        where rn_grade_band = 1
    ),

    enrollments as (
        select
            e.*,

            es.school_abbreviation as most_recent_es,

            ms.school_abbreviation as most_recent_ms,
        from {{ ref("int_extracts__student_enrollments") }} as e
        left join
            most_recent_school_by_grade_band as es
            on e.student_number = es.student_number
            and e._dbt_source_project = es._dbt_source_project
            and es.grade_band = 'ES'
        left join
            most_recent_school_by_grade_band as ms
            on e.student_number = ms.student_number
            and e._dbt_source_project = ms._dbt_source_project
            and ms.grade_band = 'MS'
        where e.enroll_status in (0, -1) and e.rn_all = 1
    )

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

    -- Prior-level history only. The picks above include the student's current
    -- enrollment, so blank every band at or below the band they are in now.
    -- That makes these read as "KIPP schools attended before this one". Keyed
    -- on grade_level rather than school_level for the off-model reason above.
    -- The es_attended and ms_attended columns on
    -- int_extracts__student_enrollments are NOT these -- they band by
    -- school_level and include the current school.
    if(grade_level between 0 and 4, null, most_recent_es) as es_attended,
    if(grade_level between 0 and 8, null, most_recent_ms) as ms_attended,
from enrollments
