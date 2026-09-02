-- grain projection, not dup-masking: academic_year/region/schoolid/grade_level
select distinct
    _dbt_source_project,
    academic_year,
    region,
    schoolid,
    grade_level,

    'powerschool' as school_source,

from {{ ref("int_powerschool__student_enrollment_union") }}
-- 999999 is the graduated-students placeholder
where schoolid != 999999 and grade_level is not null

union all

-- grain projection, not dup-masking: academic_year/region/schoolid/grade_level
select distinct
    _dbt_source_project,
    academic_year,
    region,
    ps_schoolid as schoolid,
    grade_level,

    'focus' as school_source,

from {{ ref("int_focus__student_enrollment_roster") }}
-- A fixed boundary, not the current year -- do not swap for current_academic_year.
-- Focus reaches back to AY2018, but Miami's PowerSchool archive owns through
-- AY2025. ps_schoolid is null for Focus's non-instructional schools (Applicants).
where academic_year >= 2026 and ps_schoolid is not null
