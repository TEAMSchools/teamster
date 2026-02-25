select
    enrollment_academic_year,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    goal_granularity,
    goal_type,
    goal_name,
    goal_value,

from
    {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
    /*
union all

select
    enrollment_academic_year,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    goal_granularity,
    'Pending Offers' as goal_type,
    'Pending Offers' as goal_name,
    0 as goal_value,

    1 as rn_groupings,

from {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
where goal_granularity = 'School/Grade Level' and goal_type = 'Applications'

union all

select
    enrollment_academic_year,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    goal_granularity,
    'Pending Offers' as goal_type,
    '<= 4 Days' as goal_name,
    0 as goal_value,

    1 as rn_groupings,

from {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
where
    goal_granularity = 'School/Grade Level' and goal_type = 'Applications'
   
union all

select
    enrollment_academic_year,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    goal_granularity,
    'Pending Offers' as goal_type,
    '>= 5 & <= 10 Days' as goal_name,
    0 as goal_value,

    1 as rn_groupings,

from {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
where goal_granularity = 'School/Grade Level' and goal_type = 'Applications'

union all

select
    enrollment_academic_year,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    goal_granularity,
    'Pending Offers' as goal_type,
    '> 10 Days' as goal_name,
    0 as goal_value,

    1 as rn_groupings,

from {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
where goal_granularity = 'School/Grade Level' and goal_type = 'Applications'

union all

select
    enrollment_academic_year,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    goal_granularity,
    'Overall Conversion' as goal_type,
    'Before FDOS' as goal_name,
    0 as goal_value,

    1 as rn_groupings,

from {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
where goal_granularity = 'School/Grade Level' and goal_type = 'Applications'

union all

select
    enrollment_academic_year,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    goal_granularity,
    'Overall Conversion' as goal_type,
    'On FDOS' as goal_name,
    0 as goal_value,

    1 as rn_groupings,

from {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
where goal_granularity = 'School/Grade Level' and goal_type = 'Applications'

union all

select
    enrollment_academic_year,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    goal_granularity,
    'Overall Conversion' as goal_type,
    'On Oct 1st' as goal_name,
    0 as goal_value,

    1 as rn_groupings,

from {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
where goal_granularity = 'School/Grade Level' and goal_type = 'Applications'

union all

select
    enrollment_academic_year,
    region,
    school_level,
    schoolid,
    school,
    grade_level,
    goal_granularity,
    'Overall Conversion' as goal_type,
    'On Oct 15th' as goal_name,
    0 as goal_value,

    1 as rn_groupings,

from {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
where goal_granularity = 'School/Grade Level' and goal_type = 'Applications'

union all

select
    enrollment_academic_year,
    region,
    school_level,
    0 as schoolid,
    'No School Assigned' as school,
    grade_level,
    goal_granularity,
    'Inquiries' as goal_type,
    'Inquiries' as goal_name,
    0 as goal_value,

    1 as rn_groupings,

from {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
where goal_granularity = 'Region/Grade Level' and goal_type = 'Applications'

union all

select
    enrollment_academic_year,
    region,
    school_level,
    0 as schoolid,
    'No School Assigned' as school,
    grade_level,
    goal_granularity,
    goal_type,
    'Inquiries' as goal_name,
    0 as goal_value,

    1 as rn_groupings,

from {{ source("google_sheets", "src_google_sheets__finalsite__goals") }}
where goal_granularity = 'Region/Grade Level' and goal_type = 'Applications'
*/