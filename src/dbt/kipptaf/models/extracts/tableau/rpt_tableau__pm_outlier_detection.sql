with
    score_dates as (
        select
            od.observer_employee_number,
            od.academic_year,
            od.form_term as reporting_term,
            od.is_iqr_outlier_current,
            od.is_iqr_outlier_global,
            od.cluster_current,
            od.cluster_global,
            od.tree_outlier_current,
            od.tree_outlier_global,
            od.pc1_current,
            od.pc1_global,
            od.pc1_variance_explained_current,
            od.pc1_variance_explained_global,
            od.pc2_current,
            od.pc2_global,
            od.pc2_variance_explained_current,
            od.pc2_variance_explained_global,
            od.overall_score as manager_overall_score,
            od.etr1a,
            od.etr1b,
            od.etr2a,
            od.etr2b,
            od.etr2c,
            od.etr2d,
            od.etr3a,
            od.etr3b,
            od.etr3c,
            od.etr3d,
            od.etr4a,
            od.etr4b,
            od.etr4c,
            od.etr4d,
            od.etr4e,
            od.etr4f,
            od.etr5a,
            od.etr5b,
            od.etr5c,
            od.so1,
            od.so2,
            od.so3,
            od.so4,
            od.so5,
            od.so6,
            od.so7,
            od.so8,

            timestamp(rt.end_date) as end_date_timestamp,
        from {{ ref("stg_performance_management__outlier_detection") }} as od
        inner join
            {{ ref("stg_reporting__terms") }} as rt
            on od.academic_year = rt.academic_year
            and od.form_term = rt.code
            and rt.type in ('PM', 'PMS')
            and rt.name like '%Coach%'
    ),

    score_aggs as (
        select
            obs.employee_number,
            obs.observer_employee_number,
            obs.academic_year,
            obs.term_code,

            srh.department_home_name,
            srh.job_title,
            srh.home_work_location_name,
            srh.preferred_name_lastfirst,
            srh.report_to_preferred_name_lastfirst,

            avg(obs.observation_score) as overall_score,
        from {{ ref("int_performance_management__observation_details") }} as obs
        inner join
            {{ ref("base_people__staff_roster_history") }} as srh
            on obs.employee_number = srh.employee_number
            and obs.observed_at_timestamp
            between srh.work_assignment_start_timestamp
            and srh.work_assignment_end_timestamp
            and obs.rubric_name like '%Coach ETR%'
        group by
            obs.employee_number,
            obs.observer_employee_number,
            obs.academic_year,
            obs.term_code,
            srh.department_home_name,
            srh.job_title,
            srh.home_work_location_name,
            srh.preferred_name_lastfirst,
            srh.report_to_preferred_name_lastfirst
    )

select
    sd.observer_employee_number,
    sd.academic_year,
    sd.reporting_term,
    sd.pc1_current,
    sd.pc1_global,
    sd.pc1_variance_explained_current,
    sd.pc1_variance_explained_global,
    sd.pc2_current,
    sd.pc2_global,
    sd.pc2_variance_explained_current,
    sd.pc2_variance_explained_global,
    sd.manager_overall_score,
    sd.etr1a,
    sd.etr1b,
    sd.etr2a,
    sd.etr2b,
    sd.etr2c,
    sd.etr2d,
    sd.etr3a,
    sd.etr3b,
    sd.etr3c,
    sd.etr3d,
    sd.etr4a,
    sd.etr4b,
    sd.etr4c,
    sd.etr4d,
    sd.etr4e,
    sd.etr4f,
    sd.etr5a,
    sd.etr5b,
    sd.etr5c,
    sd.so1,
    sd.so2,
    sd.so3,
    sd.so4,
    sd.so5,
    sd.so6,
    sd.so7,
    sd.so8,

    srh.preferred_name_lastfirst as observer_name,
    srh.department_home_name as observer_department,
    srh.job_title as observer_job_title,
    srh.home_work_location_name as observer_location,
    srh.report_to_preferred_name_lastfirst as observer_manager,

    sa.employee_number as teacher_employee_number,
    sa.preferred_name_lastfirst as teacher_name,
    sa.department_home_name as teacher_department,
    sa.job_title as teacher_job_title,
    sa.home_work_location_name as teacher_location,
    sa.report_to_preferred_name_lastfirst as teacher_manager,
    sa.overall_score as teacher_overall_score,

    if(sd.is_iqr_outlier_current, 'outlier', 'not outlier') as iqr_current,
    if(sd.is_iqr_outlier_global, 'outlier', 'not outlier') as iqr_global,
    if(sd.cluster_current = -1, 'outlier', 'not outlier') as cluster_current,
    if(sd.cluster_global = -1, 'outlier', 'not outlier') as cluster_global,
    if(sd.tree_outlier_current = -1, 'outlier', 'not outlier') as tree_current,
    if(sd.tree_outlier_global = -1, 'outlier', 'not outlier') as tree_global,
from score_dates as sd
inner join
    {{ ref("base_people__staff_roster_history") }} as srh
    on sd.observer_employee_number = srh.employee_number
    and sd.end_date_timestamp
    between srh.work_assignment_start_timestamp and srh.work_assignment_end_timestamp
inner join
    score_aggs as sa
    on sd.observer_employee_number = sa.observer_employee_number
    and sd.academic_year = sa.academic_year
    and sd.reporting_term = sa.term_code
