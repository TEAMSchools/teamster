select
    f.finalsite_student_id,
    f.status_start_date,
    f.status_end_date,
    f.enrollment_year,
    f.enrollment_academic_year,
    f.enrollment_academic_year_display,
    f.sre_academic_year,
    f.sre_academic_year_start,
    f.sre_academic_year_end,
    f.status,
    f.first_name,
    f.last_name,
    f.grade_level_name,
    f.grade_level,
    f.detailed_status,
    f.days_in_status,
    f.rn,
    f.enrollment_type_raw,
    f.latest_powerschool_student_number as powerschool_student_number,

    x.region,
    x.abbreviation as school,
    x.powerschool_school_id as schoolid,

    xl.region as latest_region,
    xl.powerschool_school_id as latest_schoolid,

    'KTAF' as org,

    coalesce(xl.abbreviation, 'No School Assigned') as latest_school,

from {{ ref("stg_finalsite__status_report") }} as f
left join
    {{ ref("stg_google_sheets__people__location_crosswalk") }} as x on f.school = x.name
left join
    {{ ref("stg_google_sheets__people__location_crosswalk") }} as xl
    on f.latest_school = xl.name
