with
    smg_glows_grows as (
        select
            o.observation_id,
            max(
                if(
                    od.measurement_name like '%Glow%',
                    od.measurement_dropdown_selection,
                    null
                )
            ) as glow_area,
            max(
                if(
                    od.measurement_name like '%Grow%',
                    od.measurement_dropdown_selection,
                    null
                )
            ) as growth_area,
            max(
                if(od.measurement_name like '%Glow%', od.measurement_comments, null)
            ) as glow_notes,
            max(
                if(od.measurement_name like '%Grow%', od.measurement_comments, null)
            ) as growth_notes,

        from {{ ref("int_performance_management__observations") }} as o
        inner join
            {{ ref("int_performance_management__observation_details") }} as od
            on o.observation_id = od.observation_id
        where o.observation_type_abbreviation = 'TDT'
        group by o.observation_id
    ),

    pm_scores as (
        select
            employee_number,
            academic_year,
            max(case when term_code = 'PM1' then observation_score end) as pm1,
            max(case when term_code = 'PM2' then observation_score end) as pm2,
            max(case when term_code = 'PM3' then observation_score end) as pm3,
        from {{ ref("int_performance_management__observations") }}
        where term_code in ('PM1', 'PM2', 'PM3')
        group by employee_number, academic_year
    ),

    tir_etr as (
        select
            o.employee_number,
            o.academic_year,
            avg(case when od.term_code = 'PM1' then od.row_score end) as pm1,
            avg(case when od.term_code = 'PM2' then od.row_score end) as pm2,
            avg(case when od.term_code = 'PM3' then od.row_score end) as pm3,
        from {{ ref("int_performance_management__observations") }} as o
        left join
            {{ ref("int_performance_management__observation_details") }} as od
            on o.observation_id = od.observation_id
        where
            od.observation_type_abbreviation in ('PM', 'PMS')
            and od.measurement_name not like '%4%'
            and od.measurement_name not like '%5%'
            and od.measurement_name not like '%S&O%'
        group by o.employee_number, o.academic_year

    ),

    pm_etr as (
        select
            o.employee_number,
            o.academic_year,
            avg(case when od.term_code = 'PM1' then od.row_score end) as pm1,
            avg(case when od.term_code = 'PM2' then od.row_score end) as pm2,
            avg(case when od.term_code = 'PM3' then od.row_score end) as pm3,
        from {{ ref("int_performance_management__observations") }} as o
        left join
            {{ ref("int_performance_management__observation_details") }} as od
            on o.observation_id = od.observation_id
        where
            od.observation_type_abbreviation in ('PM', 'PMS')
            and od.measurement_name not like '%S&O%'
        group by o.employee_number, o.academic_year
    ),

    tir_so as (
        select
            o.employee_number,
            o.academic_year,
            avg(case when od.term_code = 'PM1' then od.row_score end) as pm1,
            avg(case when od.term_code = 'PM2' then od.row_score end) as pm2,
            avg(case when od.term_code = 'PM3' then od.row_score end) as pm3,
        from {{ ref("int_performance_management__observations") }} as o
        left join
            {{ ref("int_performance_management__observation_details") }} as od
            on o.observation_id = od.observation_id
        where
            od.observation_type_abbreviation = 'PMS'
            and od.measurement_name like '%S&O%'
        group by o.employee_number, o.academic_year
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
            o.observation_notes,

            od.row_score,
            od.measurement_name,
            od.strand_name,
            od.measurement_dropdown_selection,
            od.measurement_comments,

            gg.glow_area,
            gg.growth_area,
            gg.glow_notes,
            gg.growth_notes,
        from {{ ref("int_performance_management__observations") }} as o
        left join
            {{ ref("int_performance_management__observation_details") }} as od
            on o.observation_id = od.observation_id
        left join smg_glows_grows as gg on o.observation_id = gg.observation_id
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
            /* grades not noted in archive data*/
            null as observation_grade,
            td.observation_notes,
            td.row_score,
            td.measurement_name,
            td.strand_name,
            td.text_box as measurement_dropdown_selection,
            td.text_box as measurement_comments,
            td.glow_area,
            td.growth_area,
            td.glow_notes,
            td.growth_notes,
        from {{ ref("int_performance_management__teacher_development") }} as td
    )

select
    td.employee_number,
    td.observer_employee_number,
    td.observation_id,
    td.rubric_name,
    td.observation_score,
    td.observed_at,
    td.academic_year,
    td.observation_type,
    td.observation_type_abbreviation,
    td.observation_subject,
    td.observation_grade,
    td.observation_notes,
    td.row_score,
    td.measurement_name,
    td.strand_name,
    td.measurement_dropdown_selection,
    td.measurement_comments,
    td.glow_area,
    td.growth_area,
    td.glow_notes,
    td.growth_notes,

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

    tgl.grade_level as grade_taught,

    os.final_score as performance_management_final_score,
    os.final_tier as performance_management_final_tier,

    sr.formatted_name as observer_name,

    pm.pm1,
    pm.pm2,
    pm.pm3,

    pme.pm1 as smg_etr_pm1,
    pme.pm2 as smg_etr_pm2,
    pme.pm3 as smg_etr_pm3,

    etr.pm1 as tir_etr_pm1,
    etr.pm2 as tir_etr_pm2,
    etr.pm3 as tir_etr_pm3,

    so.pm1 as tir_so_pm1,
    so.pm2 as tir_so_pm2,
    so.pm3 as tir_so_pm3,

    (etr.pm1 * .8 + so.pm1 * .2) as tir_pm1,
    (etr.pm2 * .8 + so.pm2 * .2) as tir_pm2,
    (etr.pm3 * .8 + so.pm3 * .2) as tir_pm3,

    if(
        sr.home_department_name = 'New Teacher Development', 'TDT', 'NTNC'
    ) as observer_team,
    -- trunk-ignore(sqlfluff/LT01) 
    date_trunc(td.observed_at, week(monday)) as week_start,
from observations_td_union as td
left join
    {{ ref("int_people__staff_roster_history") }} as srh
    on td.employee_number = srh.employee_number
    and td.observed_at between srh.effective_date_start and srh.effective_date_end
left join
    {{ ref("int_powerschool__teacher_grade_levels") }} as tgl
    on srh.powerschool_teacher_number = tgl.teachernumber
    and td.academic_year = tgl.academic_year
    and tgl.grade_level_rank = 1
left join
    {{ ref("int_performance_management__overall_scores") }} as os
    on td.employee_number = os.employee_number
    and td.academic_year = os.academic_year
left join
    {{ ref("int_people__staff_roster") }} as sr
    on td.observer_employee_number = sr.employee_number
left join
    pm_scores as pm
    on td.employee_number = pm.employee_number
    and td.academic_year = pm.academic_year
left join
    pm_etr as pme
    on td.employee_number = pme.employee_number
    and td.academic_year = pme.academic_year
left join
    tir_etr as etr
    on td.employee_number = etr.employee_number
    and td.academic_year = etr.academic_year
    and srh.job_title = 'Teacher in Residence'
left join
    tir_so as so
    on td.employee_number = so.employee_number
    and td.academic_year = so.academic_year
    and srh.job_title = 'Teacher in Residence'
