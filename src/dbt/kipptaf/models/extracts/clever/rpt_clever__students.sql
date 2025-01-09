select
    sr.last_name,
    sr.middle_name,
    sr.first_name,
    sr.gender,
    sr.cohort as graduation_year,
    sr.ethnicity as race,
    sr.student_email_google as student_email,
    sr.student_web_id as username,
    sr.gifted_and_talented as ext__gifted,

    sc.relationship_type as contact_relationship,

    gpa.cumulative_y1_gpa as unweighted_gpa,
    gpa.cumulative_y1_gpa_unweighted as weighted_gpa,

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

    coalesce(sc.contact_name, sc.person_type) as contact_name,

    left(regexp_replace(sc.contact, r'\W', ''), 10) as contact_phone,

    if(sr.lep_status, 'Y', 'N') as ell_status,
    if(sr.spedlep in ('SPED', 'SPED SPEECH'), 'Y', 'N') as iep_status,
    if(sr.region = 'Miami', sr.fleid, sr.state_studentnumber) as state_id,
    if(sr.grade_level = 0, 'Kindergarten', cast(sr.grade_level as string)) as grade,

    if(
        sc.person_type in ('mother', 'father', 'contact1', 'contact2'),
        'primary',
        sc.person_type
    ) as contact_type,

    case
        when sc.contact_type = 'home'
        then 'Home'
        when sc.contact_type = 'mobile'
        then 'Cell'
        when sc.contact_type = 'daytime'
        then 'Work'
    end as contact_phone_type,
from {{ ref("base_powerschool__student_enrollments") }} as sr
left join
    {{ ref("int_powerschool__student_contacts") }} as sc
    on sr.student_number = sc.student_number
    and {{ union_dataset_join_clause(left_alias="sr", right_alias="sc") }}
    and sc.contact_category = 'Phone'
    and sc.person_type != 'self'
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gpa
    on sr.studentid = gpa.studentid
    and sr.schoolid = gpa.schoolid
    and {{ union_dataset_join_clause(left_alias="sr", right_alias="gpa") }}
where
    sr.academic_year = {{ var("current_academic_year") }}
    and sr.rn_year = 1
    and not sr.is_out_of_district
    and sr.grade_level != 99
