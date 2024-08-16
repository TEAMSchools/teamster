with
    smg_glows_grows as (
        select
            o.observation_id,

            max(if(od.measurement_name like '%Glow%', od.text_box, null)) as glow_area,
            max(
                if(od.measurement_name like '%Grow%', od.text_box, null)
            ) as growth_area,
        from {{ ref("int_performance_management__observations") }} as o
        inner join
            {{ ref("int_performance_management__observation_details") }} as od
            on o.observation_id = od.observation_id
        where o.observation_type_abbreviation = 'TDT'
        group by o.observation_id
    ),

    observations_td_union as (
        select
            o.employee_number,
            o.observer_employee_number,

            null as observer_name,

            o.observation_id,
            o.rubric_name,
            o.observation_score,
            o.observed_at,
            o.academic_year,
            o.observation_type,
            o.observation_type_abbreviation,
            o.observation_course as observation_subject,
            o.observation_grade,

            od.row_score,
            od.measurement_name,
            od.strand_name,
            od.text_box,

            null as growth_area,
            null as glow_area,
        from {{ ref("int_performance_management__observations") }} as o
        left join
            {{ ref("int_performance_management__observation_details") }} as od
            on o.observation_id = od.observation_id
        where o.observation_type_abbreviation = 'TDT' and od.row_score is not null

        union all

        select
            td.employee_number,
            td.observer_employee_number,
            td.observer_name,
            td.observation_id,
            td.rubric_name,
            td.observation_score,
            td.observed_at,
            td.academic_year,
            td.observation_type,
            td.observation_type_abbreviation,
            td.observation_subject,

            null as observation_grade,

            td.row_score,
            td.measurement_name,
            td.strand_name,
            td.text_box,

            coalesce(gg.growth_area, td.growth_area) as growth_area,
            coalesce(gg.growth_area, td.glow_area) as glow_area,
        from {{ ref("int_performance_management__teacher_development") }} as td
        left join smg_glows_grows as gg on gg.observation_id = td.observation_id
    )

select
    td.employee_number,
    td.observer_employee_number,
    td.observer_name,
    td.observation_id,
    td.rubric_name,
    td.observation_score,
    td.observed_at,
    td.academic_year,
    td.observation_type,
    td.observation_type_abbreviation,
    td.observation_subject,
    td.observation_grade,
    td.row_score,
    td.measurement_name,
    td.strand_name,
    td.text_box,
    td.growth_area,
    td.glow_area,

    srh.preferred_name_lastfirst as teammate,
    srh.business_unit_home_name as entity,
    srh.home_work_location_name as `location`,
    srh.home_work_location_grade_band as grade_band,
    srh.department_home_name as department,
    srh.primary_grade_level_taught as grade_taught,
    srh.job_title,
    srh.report_to_preferred_name_lastfirst as manager,
    srh.worker_original_hire_date,
    srh.assignment_status,
    srh.sam_account_name,
    srh.report_to_sam_account_name,

    os.final_score as performance_management_final_score,
    os.final_tier as performance_management_final_tier,

    if(
        srh.department_home_name = 'New Teacher Development', 'TDT', 'NTNC'
    ) as observer_team,
from observations_td_union as td
left join
    {{ ref("base_people__staff_roster_history") }} as srh
    on td.employee_number = srh.employee_number
    and td.observed_at
    between srh.work_assignment_start_date and srh.work_assignment_end_date
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on td.employee_number = os.employee_number
    and td.academic_year = os.academic_year
