select
    _dbt_source_relation,
    academic_year,
    region,
    schoolid,
    school_abbreviation as school,
    student_number,
    lastfirst as student_name,
    grade_level,
    cohort,
    enroll_status,
    is_out_of_district,
    gender,
    lunch_status,

    'KTAF' as `organization`,

    if(region = 'Miami', fleid, state_studentnumber) as state_studentnumber,

    if(spedlep like '%SPED%', 'Has IEP', 'No IEP') as iep_status,

    case
        when school_level in ('ES', 'MS')
        then advisory_name
        when school_level = 'HS'
        then advisor_lastfirst
    end as advisory,

    case
        when region in ('Camden', 'Newark') then 'NJ' when region = 'Miami' then 'FL'
    end as state,

from {{ ref("base_powerschool__student_enrollments") }}
where rn_year = 1 and schoolid != 999999
