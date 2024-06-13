select
    sr.employee_number,
    sr.assignment_status,
    sr.preferred_name_lastfirst,
    sr.home_work_location_name,
    sr.home_work_location_grade_band,
    sr.job_title,
    sr.mail,
    sr.google_email,
    sr.report_to_mail,
    sr.report_to_google_email,
    sr.worker_original_hire_date,
    sr.business_unit_home_name,

    coalesce(
        sr.primary_grade_level_taught, sr.department_home_name
    ) as grade_department,
    coalesce(lc.region, sr.business_unit_home_name) as location_entity,
    coalesce(lc.abbreviation, sr.home_work_location_name) as location_shortname,

    coalesce(cc.name, sr.home_work_location_name) as campus,

/* ITR Response */
/* Final PM Score */

from {{ ref("base_people__staff_roster") }} as sr
inner join
    {{ ref("stg_people__location_crosswalk") }} as lc
    on sr.home_work_location_name = lc.clean_name
left join
    {{ ref("stg_people__campus_crosswalk") }} as cc
    on sr.home_work_location_name = cc.location_name
/*join to nonrenewal table*/
