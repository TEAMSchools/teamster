with
    date_spine as (
        select
            week_start_monday,
            week_end_sunday,
            schoolid,
            academic_year,

            min(week_start_monday) over (
                partition by academic_year, schoolid
            ) as first_day_of_ay,
        from {{ ref("int_powerschool__calendar_week") }}
        where academic_year >= 2025  /* 1st year for topline */
    ),

    staff_roster_history as (
        select
            employee_number,
            effective_date_start,
            effective_date_end,
            worker_termination_date,
            powerschool_teacher_number,
            home_business_unit_name,
            home_work_location_powerschool_school_id,
            home_work_location_name,
            home_department_name,
            job_title,
            assignment_status,
            reports_to_user_principal_name,

            case
                when
                    home_business_unit_name = 'KIPP TEAM and Family Schools Inc.'
                    and coalesce(home_work_location_powerschool_school_id, 0) = 0
                then 133570965
                when
                    home_business_unit_name = 'TEAM Academy Charter School'
                    and coalesce(home_work_location_powerschool_school_id, 0) = 0
                then 133570965
                when
                    home_business_unit_name = 'KIPP Miami'
                    and coalesce(home_work_location_powerschool_school_id, 0) = 0
                then 30200803
                when
                    home_business_unit_name = 'KIPP Cooper Norcross Academy'
                    and coalesce(home_work_location_powerschool_school_id, 0) = 0
                then 179901
                else home_work_location_powerschool_school_id
            end as schoolid,
        from {{ ref("int_people__staff_roster_history") }}
        where primary_indicator and assignment_status = 'Active'
    )

select
    srh.employee_number,
    srh.powerschool_teacher_number,
    srh.home_business_unit_name,
    srh.home_work_location_powerschool_school_id,
    srh.home_work_location_name,
    srh.home_department_name,
    srh.job_title,
    srh.assignment_status,
    srh.reports_to_user_principal_name,

    ds.academic_year,
    ds.week_start_monday,
    ds.week_end_sunday,
from staff_roster_history as srh
inner join
    date_spine as ds
    on srh.schoolid = ds.schoolid
    /* if a teacher switches schools mid-week, they will be counted in the receiving
    school only for that week */
    and ds.week_end_sunday between srh.effective_date_start and srh.effective_date_end
    {# inner join
    date_spine as ds
    on srh.ps_id_for_cal_mapping = ds.schoolid
    and (
        srh.effective_date_start between ds.week_start_monday and ds.week_end_sunday
        or srh.effective_date_end between ds.week_start_monday and ds.week_end_sunday
        or (
            (
                ds.week_start_monday
                between srh.effective_date_start and srh.effective_date_end
            )
            and (
                ds.week_end_sunday
                between srh.effective_date_start and srh.effective_date_end
            )
        )
    )
    and (
        srh.worker_termination_date is null
        or srh.worker_termination_date > ds.first_day_of_ay
    ) -#}
    
