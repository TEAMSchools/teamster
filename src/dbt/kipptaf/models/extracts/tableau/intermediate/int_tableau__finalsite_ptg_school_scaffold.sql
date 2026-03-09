/* dont have a better location where only one schoolid matches a single school
   name */
select distinct
    s.academic_year,
    s.org,
    s.region,
    s.schoolid,
    s.school,
    s.grade_level,

    x.grade_band as school_level,

    enrollment_type,

    'School' as goal_granularity,

from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as s
left join
    {{ ref("stg_google_sheets__people__location_crosswalk") }} as x
    on s.schoolid = x.powerschool_school_id
cross join unnest(['All', 'New', 'Returning']) as enrollment_type
/* hardcoding year to avoid issues when PS rollsover and next year because
   current year */
where s.academic_year = 2026 and s.grade_level = -1

union all

/* dont have a better location where only one schoolid matches a single school
   name */
select distinct
    s.academic_year,
    s.org,
    s.region,
    s.schoolid,
    s.school,
    s.grade_level,

    s.school_level,

    enrollment_type,

    'School/Grade Level' as goal_granularity,

from {{ ref("stg_google_sheets__finalsite__school_scaffold") }} as s
cross join unnest(['All', 'New', 'Returning']) as enrollment_type
/* hardcoding year to avoid issues when PS rollsover and next year because
   current year */
where s.academic_year = 2026 and s.grade_level != -1 and s.schoolid != 0
