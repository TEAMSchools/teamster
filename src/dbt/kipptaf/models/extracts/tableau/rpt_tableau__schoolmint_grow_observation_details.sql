with
    tir_previous as (
        select srh.employee_number, true as prior_year_tir,
        from {{ ref("base_people__staff_roster_history") }} as srh
        where
            date(srh.work_assignment_start_date)
            >= date({{ var("current_academic_year") }} - 1, 07, 01)
            and srh.assignment_status = 'Active'
            and srh.job_title = 'Teacher in Residence'
        group by employee_number
    )

/* tracking for current year */
select
    srh.employee_number,
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

    t.type as tracking_type,
    t.code as tracking_code,
    t.name as tracking_rubric,
    t.academic_year as tracking_academic_year,
    t.is_current,

    os.final_score,
    os.final_tier,

    od.observer_employee_number,
    od.observation_id,
    od.rubric_name,
    od.observation_score,
    od.strand_score,
    od.glows,
    od.grows,
    od.locked,
    od.observed_at,
    od.academic_year,
    od.observation_type,
    od.observation_type_abbreviation,
    od.term_code,
    od.term_name,
    od.row_score,
    od.measurement_name,
    od.strand_name,
    od.text_box,
    od.overall_tier,
    null as etr_score,
    null as so_score,

    sro.preferred_name_lastfirst as observer_name,

    if(od.observation_id is not null, 1, 0) as is_observed,
    if(
        od.observation_score = 1 and od.observation_type_abbreviation = 'WT', 1, 0
    ) as met_goal_miami,
    case
        when srh.business_unit_home_name = 'KIPP Miami'
        then true
        when srh.job_title = 'Teacher in Residence'
        then true
        when
            srh.worker_original_hire_date
            >= date({{ var("current_academic_year") }}, 4, 1)
        then true
        when tir.prior_year_tir is true
        then true
        else false
    end as boy_eligible,
from {{ ref("base_people__staff_roster_history") }} as srh
inner join
    {{ ref("stg_reporting__terms") }} as t
    on srh.business_unit_home_name = t.region
    and (
        t.start_date between date(srh.work_assignment_start_date) and date(
            srh.work_assignment_end_date
        )
        or t.end_date between date(srh.work_assignment_start_date) and date(
            srh.work_assignment_end_date
        )
    )
    and t.type in ('PMS', 'PMC', 'TR', 'O3', 'WT')
    and t.academic_year = {{ var("current_academic_year") }}
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on srh.employee_number = os.employee_number
    and t.academic_year = os.academic_year
left join
    {{ ref("int_performance_management__observation_details") }} as od
    on srh.employee_number = od.employee_number
    and t.type = od.observation_type_abbreviation
    and od.observed_at between t.start_date and t.end_date
left join
    {{ ref("base_people__staff_roster") }} as sro
    on od.observer_employee_number = sro.employee_number
left join tir_previous as tir on srh.employee_number = tir.employee_number
where
    srh.job_title in ('Teacher', 'Teacher in Residence', 'Learning Specialist')
    and srh.assignment_status = 'Active'

union all

/* actual responses from past years*/
select
    srh.employee_number,
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

    null as tracking_type,
    null as tracking_code,
    null as tracking_rubric,
    null as tracking_academic_year,
    false as is_current,

    os.final_score,
    os.final_tier,

    od.observer_employee_number,
    od.observation_id,
    od.rubric_name,
    od.observation_score,
    od.strand_score,
    od.glows,
    od.grows,
    od.locked,
    od.observed_at,
    od.academic_year,
    od.observation_type,
    od.observation_type_abbreviation,
    od.term_code,
    od.term_name,
    od.row_score,
    od.measurement_name,
    od.strand_name,
    od.text_box,
    od.overall_tier,
    od.etr_score,
    od.so_score,

    sro.preferred_name_lastfirst as observer_name,

    if(od.observation_id is not null, 1, 0) as is_observed,
    if(
        od.observation_score = 1 and od.observation_type_abbreviation = 'WT', 1, 0
    ) as met_goal_miami,
    null as boy_eligible,
from {{ ref("base_people__staff_roster_history") }} as srh
inner join
    {{ ref("int_performance_management__observation_details") }} as od
    on srh.employee_number = od.employee_number
    and od.observed_at
    between date(srh.work_assignment_start_date) and date(srh.work_assignment_end_date)
    and srh.assignment_status = 'Active'
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on srh.employee_number = os.employee_number
    and od.academic_year = os.academic_year
left join
    {{ ref("base_people__staff_roster") }} as sro
    on od.observer_employee_number = sro.employee_number
