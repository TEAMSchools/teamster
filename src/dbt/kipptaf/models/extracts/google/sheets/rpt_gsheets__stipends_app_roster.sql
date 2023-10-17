select
    sr.employee_number,
    sr.payroll_group_code,
    sr.worker_id,
    sr.payroll_file_number as file_number,
    sr.position_id,
    sr.job_title,
    sr.home_work_location_name as location,
    sr.department_home_name as department,
    sr.preferred_name_lastfirst as preferred_name,
    sr.user_principal_name as email,
    sr.google_email,
    sr.assignment_status as status,
    sr.business_unit_home_name as region,
    sr.worker_termination_date,
    coalesce(sr.home_work_location_abbreviation,sr.home_work_location_name) as location_abbr,
    coalesce(cc.name, sr.home_work_location_name) as campus,
    case 
    when sr.home_work_location_name NOT LIKE '%Room%' and sr.department_home_name IN ('Operations','School Support') then 'operations'
    when sr.home_work_location_name NOT LIKE '%Room%' and sr.business_unit_home_name NOT LIKE '%Family%' then 'instructional'
    when sr.home_work_location_name LIKE '%Room%' and sr.business_unit_home_name NOT LIKE '%Family%' then 'special'
    when sr.home_work_location_name LIKE '%Room%' and sr.business_unit_home_name LIKE '%Family%' then 'cmo'
    else 'special'
    end as route
from {{ ref("base_people__staff_roster") }} as sr
left join
    {{ ref("stg_people__campus_crosswalk") }} as cc
    on sr.home_work_location_name = cc.location_name