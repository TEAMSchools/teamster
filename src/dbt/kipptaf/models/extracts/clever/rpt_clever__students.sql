-- noqa: disable=ST06
select
    safe_cast(sr.schoolid as string) as school_id,
    safe_cast(sr.student_number as string) as student_id,
    safe_cast(sr.student_number as string) as student_number,
    if(sr.region = 'Miami', sr.fleid, sr.state_studentnumber) as state_id,
    sr.last_name,
    sr.middle_name,
    sr.first_name,
    if(
        sr.grade_level = 0, 'Kindergarten', safe_cast(sr.grade_level as string)
    ) as grade,
    sr.gender,
    sr.cohort as graduation_year,
    format_date('%m/%d/%Y', sr.dob) as dob,
    sr.ethnicity as race,

    null as hispanic_latino,
    null as home_language,

    if(sr.lep_status, 'Y', 'N') as ell_status,

    null as frl_status,

    if(sr.spedlep in ('SPED', 'SPED SPEECH'), 'Y', 'N') as iep_status,

    null as student_street,
    null as student_city,
    null as student_state,
    null as student_zip,

    sr.student_email_google as student_email,

    sc.relationship_type as contact_relationship,
    if(
        sc.person_type in ('mother', 'father', 'contact1', 'contact2'),
        'primary',
        sc.person_type
    ) as contact_type,
    coalesce(sc.contact_name, sc.person_type) as contact_name,
    left(regexp_replace(sc.contact, r'\W', ''), 10) as contact_phone,
    case
        when sc.contact_type = 'home'
        then 'Home'
        when sc.contact_type = 'mobile'
        then 'Cell'
        when sc.contact_type = 'daytime'
        then 'Work'
    end as contact_phone_type,

    null as contact_email,
    null as contact_sis_id,

    sr.student_web_id as username,

    null as `password`,

    gpa.cumulative_y1_gpa as unweighted_gpa,
    gpa.cumulative_y1_gpa_unweighted as weighted_gpa,
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
