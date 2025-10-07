with
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
        where primary_indicator
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
    ds.is_current_week_mon_sun as is_current_week,
from staff_roster_history as srh
inner join
    {{ ref("int_powerschool__calendar_week") }} as ds
    on srh.schoolid = ds.schoolid
    and ds.week_end_sunday between srh.effective_date_start and srh.effective_date_end
    and (
        srh.worker_termination_date > ds.first_day_school_year
        or srh.worker_termination_date is null
    )
    and ds.academic_year >= 2025  /* 1st year for topline */
