-- grain projection, not dup-masking: academic_year/region/schoolid/grade_level
select distinct
    academic_year,
    region,
    schoolid,
    grade_level,

    _dbt_source_project as code_location,

    'powerschool' as school_source,

from {{ ref("int_powerschool__student_enrollment_union") }}
-- 999999 is the graduated-students placeholder
where schoolid != 999999 and grade_level is not null
