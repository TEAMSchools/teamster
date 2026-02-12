select
    f._dbt_source_relation,
    f.enrollment_year,
    f.enrollment_academic_year,
    f.enrollment_academic_year_display,
    f.sre_academic_year_start,
    f.sre_academic_year_end,
    f.extract_year,
    f.extract_datetime,
    f.region,
    f.latest_region,
    f.finalsite_student_id,
    f.latest_finalsite_student_id,
    f.first_name,
    f.last_name,
    f.grade_level_name,
    f.grade_level,
    f.latest_grade_level,
    f.status,
    f.detailed_status,
    f.status_order,
    f.status_start_date,
    f.status_end_date,
    f.days_in_status,
    f.rn,
    f.enrollment_type_raw,
    f.latest_powerschool_student_number as powerschool_student_number,

    'KTAF' as org,

    coalesce(x.powerschool_school_id, 0) as schoolid,
    coalesce(x.abbreviation, 'No School Assigned') as school,

    coalesce(xl.powerschool_school_id, 0) as latest_schoolid,
    coalesce(xl.abbreviation, 'No School Assigned') as latest_school,

    max(f.extract_datetime) over (
        partition by f.region, f.extract_year
    ) as latest_extract_datetime,

    row_number() over (
        partition by f.latest_finalsite_student_id order by f.extract_datetime desc
    ) as latest_finalsite_student_id_rn,

    first_value(f.detailed_status) over (
        partition by f.enrollment_academic_year, f.finalsite_student_id
        order by f.status_start_date desc
    ) as latest_status,

from {{ ref("stg_finalsite__status_report") }} as f
left join
    {{ ref("stg_google_sheets__people__location_crosswalk") }} as x on f.school = x.name
left join
    {{ ref("stg_google_sheets__people__location_crosswalk") }} as xl
    on f.latest_school = xl.name
