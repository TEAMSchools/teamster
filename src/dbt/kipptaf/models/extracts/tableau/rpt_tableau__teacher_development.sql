
select
    od.observer_employee_number,
    od.observation_id,
    od.rubric_name,
    od.observation_score,
    od.observed_at,
    od.academic_year,
    od.observation_type,
    od.observation_type_abbreviation,
    od.row_score,
    od.measurement_name,
    od.strand_name,
    od.text_box,
    null as observation_notes
    null as observation_subject
    null as growth_area,
    null as growth_notes,
    null as glow_area,
    null as glow_notes,
    null as observer_team,
from {{ ref("int_performance_management__observation_details") }} as od
where observation_type_abbreviation = 'TDT'

union all

select
    null as observer_employee_number,
    o.observation_id,
    concat('Teacher Development: ',o.observation_type) as rubric_name,
    average(row_score) as observation_score,
    o.observed_at,
    '2023' as academic_year,
    'Teacher Development' as observation_type,
    'TDT' as observation_type_abbreviation,
    od.row_score,
    od.measurement_name,
    od.strand_name,
    od.text_box,

    o.observation_notes,
    o.observation_subject,
    o.growth_area,
    o.growth_notes,
    o.glow_area,
    o.glow_notes,
    o.observer_team,
from {{ ref('stg_performance_management__teacher_development_observations') }} as o
left join {{ ref('stg_performance_management__teacher_development_observation_details') }} as od
on o.observation_id = od.observation_id




    -- srh.employee_number,
    -- srh.preferred_name_lastfirst as teammate,
    -- srh.business_unit_home_name as entity,
    -- srh.home_work_location_name as `location`,
    -- srh.home_work_location_grade_band as grade_band,
    -- srh.department_home_name as department,
    -- srh.primary_grade_level_taught as grade_taught,
    -- srh.job_title,
    -- srh.report_to_preferred_name_lastfirst as manager,
    -- srh.worker_original_hire_date,
    -- srh.assignment_status,
    -- srh.sam_account_name,
    -- srh.report_to_sam_account_name,

    -- sro.preferred_name_lastfirst as observer_name,
