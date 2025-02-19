with
    tir_previous as (
        select srh.employee_number, true as prior_year_tir,
        from {{ ref("int_people__staff_roster_history") }} as srh
        where
            srh.effective_date_start >= '{{ var("current_academic_year") - 1 }}-07-01'
            and srh.assignment_status = 'Active'
            and srh.job_title = 'Teacher in Residence'
        group by employee_number
    ),

    recent_leave as (
        select distinct
            srh.employee_number, t.academic_year, t.code, true as recent_leave,
        from {{ ref("int_people__staff_roster_history") }} as srh
        inner join
            {{ ref("stg_reporting__terms") }} as t
            on assignment_status_effective_date
            between date_sub(t.lockbox_date, interval 6 week) and t.lockbox_date
            and t.type = 'PMS'
            and (assignment_status = 'Leave' or assignment_status_lag = 'Leave')
    ),

    tracks as (
        select
            o.observation_id,
            max(
                if(
                    od.measurement_name like '%Teacher Moves Track%',
                    od.measurement_dropdown_selection,
                    null
                )
            ) as teacher_moves_track,
            max(
                if(
                    od.measurement_name like '%Student Habits Track%',
                    od.measurement_dropdown_selection,
                    null
                )
            ) as student_habits_track,
            max(
                if(
                    od.measurement_name like '%Number%',
                    od.measurement_dropdown_selection,
                    null
                )
            ) as number_of_kids,
        from {{ ref("int_performance_management__observations") }} as o
        inner join
            {{ ref("int_performance_management__observation_details") }} as od
            on o.observation_id = od.observation_id
        where o.observation_type_abbreviation = 'WT'
        group by o.observation_id
    )
/* tracking for current year */
select
    srh.employee_number,
    srh.formatted_name as teammate,
    srh.home_business_unit_name as entity,
    srh.home_work_location_name as `location`,
    srh.home_work_location_grade_band as grade_band,
    srh.home_department_name as department,
    srh.job_title,
    srh.reports_to_formatted_name as manager,
    srh.worker_original_hire_date,
    srh.assignment_status,
    srh.sam_account_name,
    srh.reports_to_sam_account_name as report_to_sam_account_name,

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
    od.measurement_dropdown_selection,

    tr.teacher_moves_track,
    tr.student_habits_track,
    tr.number_of_kids,
    sr.assignment_status as current_assignment_status,
    sro.formatted_name as observer_name,

    tgl.grade_level as grade_taught,

    null as etr_score,
    null as so_score,

    if(od.observation_id is not null, 1, 0) as is_observed,

    regexp_replace(od.measurement_comments, r'<[^>]+>', '') as measurement_comments,

    /* round eligibility for PM
    1: TiRs, Miami, Prior TiR (New Lead), New to KIPP
    2+3: Active six weeks prior to lockbox date */
    case
        when r.recent_leave
        then false
        when
            t.code = 'PM1'
            and (
                srh.job_title = 'Teacher in Residence'
                or tir.prior_year_tir
                or srh.home_business_unit_name = 'KIPP Miami'
                or srh.worker_original_hire_date
                between '{{ var("current_academic_year") }}-04-01' and date_sub(
                    t.lockbox_date, interval 6 week
                )
            )
        then true
        when
            t.code in ('PM2', 'PM3')
            and (
                srh.worker_original_hire_date
                <= date_sub(t.lockbox_date, interval 6 week)
            )
        then true
        else false
    end as pm_round_eligible,
from {{ ref("int_people__staff_roster_history") }} as srh
inner join
    {{ ref("stg_reporting__terms") }} as t
    on srh.home_business_unit_name = t.region
    and (
        t.start_date between srh.effective_date_start and srh.effective_date_end
        or t.end_date between srh.effective_date_start and srh.effective_date_end
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
left join tracks as tr on od.observation_id = tr.observation_id
left join
    {{ ref("int_people__staff_roster") }} as sr
    on srh.employee_number = sr.employee_number
left join
    {{ ref("int_people__staff_roster") }} as sro
    on od.observer_employee_number = sro.employee_number
left join tir_previous as tir on srh.employee_number = tir.employee_number
left join
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on srh.powerschool_teacher_number = tgl.teachernumber
    and t.academic_year = tgl.academic_year
    and tgl.grade_level_rank = 1
left join
    recent_leave as r
    on srh.employee_number = r.employee_number
    and t.academic_year = r.academic_year
    and t.code = r.code
where
    (srh.job_title like '%Teacher%' or srh.job_title like '%Learning%')
    and srh.assignment_status = 'Active'

union all

/* actual responses from past years*/
select
    srh.employee_number,
    srh.formatted_name as teammate,
    srh.home_business_unit_name as entity,
    srh.home_work_location_name as `location`,
    srh.home_work_location_grade_band as grade_band,
    srh.home_department_name as department,
    srh.job_title,
    srh.reports_to_formatted_name as manager,
    srh.worker_original_hire_date,
    srh.assignment_status,
    srh.sam_account_name,
    srh.reports_to_sam_account_name as report_to_sam_account_name,

    null as tracking_type,
    null as tracking_code,
    null as tracking_rubric,
    null as tracking_academic_year,
    false as is_current,
    null as start_date,
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
    od.measurement_dropdown_selection,

    null as teacher_moves_track,
    null as student_habits_track,
    null as number_of_kids,

    sr.assignment_status as current_assignment_status,
    sro.formatted_name as observer_name,

    tgl.grade_level as grade_taught,

    od.etr_score,
    od.so_score,

    if(od.observation_id is not null, 1, 0) as is_observed,

    regexp_replace(od.measurement_comments, r'<[^>]+>', '') as measurement_comments,

    null as pm_round_eligible,
from {{ ref("int_people__staff_roster_history") }} as srh
inner join
    {{ ref("int_performance_management__observation_details") }} as od
    on srh.employee_number = od.employee_number
    and od.observed_at between srh.effective_date_start and srh.effective_date_end
    and srh.assignment_status = 'Active'
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
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on srh.powerschool_teacher_number = tgl.teachernumber
    and od.academic_year = tgl.academic_year
    and tgl.grade_level_rank = 1
