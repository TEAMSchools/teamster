select
    sr.employee_number,
    sr.sam_account_name,
    sr.report_to_sam_account_name,
    sr.preferred_name_lastfirst as teammate,
    sr.business_unit_home_name as entity,
    sr.home_work_location_name as location,
    sr.home_work_location_grade_band as grade_band,
    sr.department_home_name as department,
    sr.primary_grade_level_taught as grade_taught,
    sr.job_title,
    sr.report_to_preferred_name_lastfirst as manager,
    sr.worker_original_hire_date,
    sr.assignment_status,
    
    rt.type,
    rt.code,
    rt.name,
    rt.start_date,
    rt.end_date,

    od.observation_id,

    sr2.preferred_name_lastfirst as observer_name,

from {{ ref("base_people__staff_roster") }} as sr
inner join
    {{ ref("stg_reporting__terms") }} as rt
    on (sr.job_title like '%Teacher%' or sr.job_title = 'Learning Specialist')
    and sr.assignment_status = 'Active'
    and rt.type in ('O3','PM','WT')
    and rt.academic_year = {{ var('current_academic_year') }}
left join
    {{ ref("int_performance_management__observation_details") }} as od
    on sr.employee_number = od.employee_number
    and rt.type = od.observation_type_abbreviation
    and od.observed_at between rt.start_date and rt.end_date
left join
    {{ ref("base_people__staff_roster") }} as sr2
    on od.observer_employee_number = sr2.employee_number