with
    contacts as (
        -- One row per (student, contact slot, phone type) for the Clever feed.
        -- Unpivots the 1+4 contact surface from int_students__contacts:
        -- contact_1 is the single reportable parent (contact_type 'primary');
        -- emergency_1..4 are emergency contacts. The Work phone prefers the
        -- typed Work number, falling back to the legacy daytime slot for
        -- PS-sourced regions. Contacts with no phone of a given type emit no
        -- row for that type.
        select
            student_number,
            _dbt_source_project,
            contact_name,
            relationship,

            phone.contact_phone_type,
            phone.contact_phone,

            if(is_emergency, 'emergency', 'primary') as contact_type,
        from {{ ref("int_students__contacts") }}
        cross join
            unnest(
                [
                    struct('Home' as contact_phone_type, phone_home as contact_phone),
                    struct('Cell' as contact_phone_type, phone_mobile as contact_phone),
                    struct(
                        'Work' as contact_phone_type,
                        coalesce(phone_work, phone_daytime) as contact_phone
                    )
                ]
            ) as phone
        where phone.contact_phone is not null
    )

select
    sr.student_last_name as last_name,
    sr.student_middle_name as middle_name,
    sr.student_first_name as first_name,
    sr.gender,
    sr.cohort as graduation_year,
    sr.ethnicity as race,
    sr.student_email,
    sr.student_web_id as username,
    sr.gifted_and_talented as ext__gifted,
    sr.cumulative_y1_gpa as weighted_gpa,
    sr.cumulative_y1_gpa_unweighted as unweighted_gpa,

    c.contact_name,
    c.relationship as contact_relationship,
    c.contact_type,
    c.contact_phone_type,

    null as hispanic_latino,
    null as home_language,
    null as frl_status,
    null as student_street,
    null as student_city,
    null as student_state,
    null as student_zip,
    null as contact_email,
    null as contact_sis_id,
    null as `password`,

    cast(sr.schoolid as string) as school_id,
    cast(sr.student_number as string) as student_id,
    cast(sr.student_number as string) as student_number,

    format_date('%m/%d/%Y', sr.dob) as dob,

    left(regexp_replace(c.contact_phone, r'\W', ''), 10) as contact_phone,

    if(sr.lep_status, 'Y', 'N') as ell_status,
    if(sr.spedlep in ('SPED', 'SPED SPEECH'), 'Y', 'N') as iep_status,
    if(sr.region = 'Miami', sr.fleid, sr.state_studentnumber) as state_id,
    if(sr.grade_level = 0, 'Kindergarten', cast(sr.grade_level as string)) as grade,
from {{ ref("int_extracts__student_enrollments") }} as sr
left join
    contacts as c
    on sr.student_number = c.student_number
    and sr._dbt_source_project = c._dbt_source_project
where
    sr.academic_year = {{ var("current_academic_year") }}
    and sr.rn_year = 1
    and not sr.is_out_of_district
    and sr.enroll_status in (0, -1)
    and sr._dbt_source_relation not like '%kipppaterson%'
