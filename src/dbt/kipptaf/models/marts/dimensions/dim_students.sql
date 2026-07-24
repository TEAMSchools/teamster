with
    students_with_region as (
        select s.*, {{ extract_region("s") }} as region,
        from {{ ref("stg_powerschool__students") }} as s
    )

select
    {{ dbt_utils.generate_surrogate_key(["s.student_number"]) }} as student_key,

    s.student_number as lea_student_identifier,

    if(
        s.region = 'Miami', s.state_studentnumber, cast(null as string)
    ) as district_student_identifier,

    if(
        s.region = 'Miami', suf.fleid, s.state_studentnumber
    ) as state_student_identifier,

    adb.id as salesforce_contact_id,

    concat(s.last_name, ', ', s.first_name) as full_name,

    s.dob as birth_date,
    s.gender as gender_identity,

    coalesce(njs.gifted_and_talented, suf.gifted_and_talented, 'N') != 'N' as is_gifted,

    case
        when s.ethnicity = 'B'
        then 'Black/African American'
        when s.ethnicity = 'H'
        then 'Hispanic or Latino'
        when s.ethnicity = 'T'
        then 'Two or More Races'
        when s.ethnicity = 'W'
        then 'White'
        when s.ethnicity = 'I'
        then 'American Indian or Alaska Native'
        when s.ethnicity = 'A'
        then 'Asian'
        when s.ethnicity = 'P'
        then 'Native Hawaiian or Other Pacific Islander'
        when s.ethnicity = 'N'
        then 'Not Hispanic or Latino'
        else 'Not Listed'
    end as race,

    case
        s.enroll_status
        when -2
        then 'Inactive'
        when -1
        then 'Pre-registered'
        when 0
        then 'Currently Enrolled'
        when 1
        then 'Inactive'
        when 2
        then 'Transferred Out'
        when 3
        then 'Graduated'
        when 4
        then 'Imported as Historical'
    end as enrollment_status,

from students_with_region as s
left join
    {{ ref("stg_kippadb__contact") }} as adb
    on s.student_number = adb.school_specific_id
left join
    {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
    on s.dcid = suf.studentsdcid
    and s._dbt_source_project = suf._dbt_source_project
left join
    {{ ref("stg_powerschool__s_nj_stu_x") }} as njs
    on s.dcid = njs.studentsdcid
    and s._dbt_source_project = njs._dbt_source_project
