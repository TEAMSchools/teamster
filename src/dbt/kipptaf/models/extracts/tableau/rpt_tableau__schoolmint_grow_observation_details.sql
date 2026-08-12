with
    recent_leave as (
        -- Joins PMS terms only, and AY2026 has no PMS PM1 term row (AY2024 and
        -- AY2025 did), so this yields PM2/PM3 rows only. The pm_round_eligible
        -- leave guard is therefore inert for PM1 until Ops re-adds that row.
        -- grain projection: every selected column is functionally determined by
        -- (employee_number, academic_year, code) -- recent_leave is a constant,
        -- so multiple matching roster-history rows collapse to one
        -- byte-identical tuple. Not a mask for upstream duplicates.
        select distinct
            srh.employee_number, t.academic_year, t.code, true as recent_leave,
        from {{ ref("int_people__staff_roster_history") }} as srh
        inner join
            {{ ref("stg_google_sheets__reporting__terms") }} as t
            on srh.assignment_status_effective_date
            between date_sub(t.lockbox_date, interval 6 week) and t.lockbox_date
            and t.type = 'PMS'
        where srh.assignment_status = 'Leave' or srh.assignment_status_lag = 'Leave'
    )

/* tracking for current year */
select
    srh.employee_number,
    srh.home_work_location_grade_band as grade_band,
    srh.reports_to_formatted_name as manager,
    srh.worker_original_hire_date,
    srh.work_assignment_actual_start_date,
    srh.assignment_status,
    srh.race_ethnicity_reporting,

    lc.location_clean_name,
    lc.campus_name,

    case
        srh.home_business_unit_name
        when 'TEAM'
        then 'TEAM Academy Charter School'
        when 'KCNA'
        then 'KIPP Cooper Norcross Academy'
        when 'MIA'
        then 'KIPP Miami'
        when 'KNJ'
        then 'KIPP TEAM and Family Schools Inc.'
        else srh.home_business_unit_name
    end as home_business_unit_name,
    srh.home_department_name,
    srh.job_function,
    srh.job_title,

    srh.mail,
    srh.user_principal_name,
    srh.sam_account_name,

    srh.reports_to_mail,
    srh.reports_to_sam_account_name,

    t.type as tracking_type,
    t.code as tracking_code,
    t.name as tracking_rubric,
    t.academic_year as tracking_academic_year,
    t.is_current,
    t.start_date,
    t.end_date,
    t.lockbox_date,

    os.final_score,
    os.final_tier,

    od.observer_employee_number,
    od.observation_id,
    od.rubric_name,
    od.observation_score,
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
    od.strand_name,
    od.measurement_name,
    od.overall_tier,
    od.observation_notes,

    sr.assignment_status as current_assignment_status,
    sr.formatted_name as teammate,

    sro.formatted_name as observer_name,

    tgl.grade_level as grade_taught,

    null as etr_score,
    null as so_score,

    em.is_leader_development_program,
    em.is_teacher_development_program,
    em.memberships,

    emo.is_leader_development_program as is_leader_development_program_observer,
    emo.is_teacher_development_program as is_teacher_development_program_observer,
    emo.memberships as memberships_observer,

    if(od.observation_id is not null, 1, 0) as is_observed,

    regexp_replace(od.measurement_comments, r'<[^>]+>', '') as measurement_comments,

    /*
        round eligibility for PM
            1: all teachers, regardless of start date
            2 & 3: Active six weeks prior to lockbox date
    */
    case
        when r.recent_leave
        then false
        when t.code = 'PM1'
        then true
        when
            t.code in ('PM2', 'PM3')
            and (
                srh.work_assignment_actual_start_date
                <= date_sub(t.lockbox_date, interval 6 week)
            )
        then true
        else false
    end as pm_round_eligible,
from {{ ref("int_people__staff_roster_history") }} as srh
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on srh.home_work_location_name = lc.location_name
inner join
    {{ ref("stg_google_sheets__reporting__terms") }} as t
    on srh.home_business_unit_name = t.region
    and (
        t.start_date
        between srh.work_assignment_actual_start_date and srh.effective_date_end
        or t.end_date
        between srh.work_assignment_actual_start_date and srh.effective_date_end
    )
    and t.academic_year = {{ var("current_academic_year") }}
    and t.type in ('PMS', 'PMC', 'TR')
/* Adding memberships for teachers*/
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on srh.employee_number = os.employee_number
    and t.academic_year = os.academic_year
/* Adding memberships for observers*/
left join
    {{ ref("int_performance_management__observation_details") }} as od
    on srh.employee_number = od.employee_number
    and t.type = od.observation_type_abbreviation
    and od.observed_at between t.start_date and t.end_date
left join
    {{ ref("int_people__staff_roster") }} as sr
    on srh.employee_number = sr.employee_number
left join
    {{ ref("int_people__staff_roster") }} as sro
    on od.observer_employee_number = sro.employee_number
left join
    {{ ref("int_students__teacher_grade_levels") }} as tgl
    on srh.powerschool_teacher_number = tgl.teachernumber
    and srh.home_work_location_dagster_code_location = tgl._dbt_source_project
    and t.academic_year = tgl.academic_year
    and tgl.grade_level_rank = 1
left join
    recent_leave as r
    on srh.employee_number = r.employee_number
    and t.academic_year = r.academic_year
    and t.code = r.code
/* Adding memberships for teachers*/
left join
    {{ ref("int_adp_workforce_now__employee_memberships_by_year") }} as em
    on t.academic_year = em.academic_year
    and sr.worker_id = em.associate_id
/* Adding memberships for observers*/
left join
    {{ ref("int_adp_workforce_now__employee_memberships_by_year") }} as emo
    on t.academic_year = emo.academic_year
    and sro.worker_id = emo.associate_id
where
    srh.primary_indicator
    and srh.assignment_status = 'Active'
    /*
        job_function (ADP codes TEACH / TIR) is not set on newly created work
        assignments, so fall back to the job title until it fills in
    */
    and (
        srh.job_function in ('Teacher', 'Teacher in Residence')
        or (
            srh.job_function is null
            and (srh.job_title like '%Teacher%' or srh.job_title like '%Learning%')
        )
    )

union all

/* actual responses from past years*/
select
    srh.employee_number,
    srh.home_work_location_grade_band as grade_band,
    srh.reports_to_formatted_name as manager,
    srh.worker_original_hire_date,
    srh.work_assignment_actual_start_date,
    srh.assignment_status,
    srh.race_ethnicity_reporting,

    lc.location_clean_name,
    lc.campus_name,

    case
        srh.home_business_unit_name
        when 'TEAM'
        then 'TEAM Academy Charter School'
        when 'KCNA'
        then 'KIPP Cooper Norcross Academy'
        when 'MIA'
        then 'KIPP Miami'
        when 'KNJ'
        then 'KIPP TEAM and Family Schools Inc.'
        else srh.home_business_unit_name
    end as home_business_unit_name,
    srh.home_department_name,
    srh.job_function,
    srh.job_title,

    srh.mail,
    srh.user_principal_name,
    srh.sam_account_name,

    srh.reports_to_mail,
    srh.reports_to_sam_account_name,

    null as tracking_type,
    null as tracking_code,
    null as tracking_rubric,
    null as tracking_academic_year,

    false as is_current,

    null as `start_date`,
    null as end_date,
    null as lockbox_date,

    os.final_score,
    os.final_tier,

    od.observer_employee_number,
    od.observation_id,
    od.rubric_name,
    od.observation_score,
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
    od.strand_name,
    od.measurement_name,
    od.overall_tier,
    od.observation_notes,

    sr.assignment_status as current_assignment_status,
    sr.formatted_name as teammate,

    sro.formatted_name as observer_name,

    tgl.grade_level as grade_taught,

    od.etr_score,
    od.so_score,

    em.is_leader_development_program,
    em.is_teacher_development_program,
    em.memberships,

    emo.is_leader_development_program as is_leader_development_program_observer,
    emo.is_teacher_development_program as is_teacher_development_program_observer,
    emo.memberships as memberships_observer,

    if(od.observation_id is not null, 1, 0) as is_observed,

    regexp_replace(od.measurement_comments, r'<[^>]+>', '') as measurement_comments,

    null as pm_round_eligible,
from {{ ref("int_people__staff_roster_history") }} as srh
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on srh.home_work_location_name = lc.location_name
inner join
    {{ ref("int_performance_management__observation_details") }} as od
    on srh.employee_number = od.employee_number
    and od.observed_at between srh.effective_date_start and srh.effective_date_end
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on srh.employee_number = os.employee_number
    and od.academic_year = os.academic_year
left join
    {{ ref("int_people__staff_roster") }} as sr
    on srh.employee_number = sr.employee_number
left join
    {{ ref("int_people__staff_roster") }} as sro
    on od.observer_employee_number = sro.employee_number
left join
    {{ ref("int_students__teacher_grade_levels") }} as tgl
    on srh.powerschool_teacher_number = tgl.teachernumber
    and srh.home_work_location_dagster_code_location = tgl._dbt_source_project
    and od.academic_year = tgl.academic_year
    and tgl.grade_level_rank = 1
left join
    {{ ref("int_adp_workforce_now__employee_memberships_by_year") }} as em
    on od.academic_year = em.academic_year
    and sr.worker_id = em.associate_id
left join
    {{ ref("int_adp_workforce_now__employee_memberships_by_year") }} as emo
    on od.academic_year = emo.academic_year
    and sro.worker_id = emo.associate_id
where srh.primary_indicator and srh.assignment_status = 'Active'
