/* tracking for current year */
select
    t.type as tracking_type,
    t.code as tracking_code,
    t.name as tracking_rubric,
    t.academic_year as tracking_academic_year,
    t.is_current,
    od.employee_number,
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

    os.final_score,
    os.final_tier,

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

    sr.sam_account_name,
    sr.report_to_sam_account_name,
    sr.preferred_name_lastfirst as observer_name,

    if(od.observation_id is not null, 1, 0) as is_observed,
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
    and t.type in ("PMS", "PMC", "TR", "O3", "WT")
    and t.academic_year = {{ var("current_academic_year") }}
left join
    {{ ref("int_performance_management__observations") }} as o
    on t.type = o.observation_type_abbreviation
    and srh.employee_number = o.employee_number
    and o.observed_at between t.start_date and t.end_date
left join
    {{ ref("int_performance_management__observation_details") }} as od
    on o.observation_id = od.observation_id
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on od.employee_number = os.employee_number
    and od.academic_year = os.academic_year
left join
    {{ ref("base_people__staff_roster") }} as sr
    on od.employee_number = sr.employee_number
left join
    {{ ref("base_people__staff_roster") }} as sr2
    on od.observer_employee_number = sr2.employee_number
where
    srh.job_title in ("Teacher", "Teacher in Residence", "Learning Specialist")
    and srh.assignment_status = "Active"

/* actual responses from past years*/
select
    null as tracking_type,
    null as tracking_code,
    null as tracking_rubric,
    null as tracking_academic_year,
    false as is_current,
    od.employee_number,
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

    os.final_score,
    os.final_tier,

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

    sr.sam_account_name,
    sr.report_to_sam_account_name,
    sr.preferred_name_lastfirst as observer_name,

    if(od.observation_id is not null, 1, 0) as is_observed,
from
    {{ ref("int_performance_management__observation_details") }} as od
    on o.observation_id = od.observation_id
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on od.employee_number = os.employee_number
    and od.academic_year = os.academic_year
inner join
    {{ ref("base_people__staff_roster_history") }} as srh
    on od.employee_number = srh.employee_number
    and od.observed_at
    between date(srh.work_assignment_start_date) and date(srh.work_assignment_end_date)
left join
    {{ ref("base_people__staff_roster") }} as sr
    on od.employee_number = sr.employee_number
left join
    {{ ref("base_people__staff_roster") }} as sr2
    on od.observer_employee_number = sr2.employee_number
