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

    /* future feeds from other data sources*/
    null as itr_response,
    null as certification_renewal_status,
    null as last_performance_management_score,
    null as smart_recruiter_id,

    coalesce(
        safe_cast(sr.primary_grade_level_taught as string), sr.department_home_name
    ) as grade_department,
    coalesce(lc.region, sr.business_unit_home_name) as location_entity,
    coalesce(lc.abbreviation, sr.home_work_location_name) as location_shortname,
    coalesce(cc.name, sr.home_work_location_name) as campus,
    case
        when
            sr.business_unit_home_name
            in ('TEAM Academy Charter School', 'KIPP Cooper Norcross Academy')
        then 'New Jersey'
        when sr.business_unit_home_name = 'KIPP Miami'
        then 'Miami'
        else 'CMO'
    end as region_state,
from {{ ref("base_people__staff_roster") }} as sr
inner join
    {{ ref("stg_people__location_crosswalk") }} as lc
    on sr.home_work_location_name = lc.name
left join
    {{ ref("stg_people__campus_crosswalk") }} as cc
    on sr.home_work_location_name = cc.location_name
