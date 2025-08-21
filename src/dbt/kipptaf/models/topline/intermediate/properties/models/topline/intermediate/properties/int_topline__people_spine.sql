with
    date_spine as (
        select
            cw.week_start_monday,
            cw.week_end_sunday,
            cw.schoolid,
            cw.academic_year,
            min(cw.week_start_monday) over (
                partition by cw.academic_year, cw.schoolid
            ) as first_day_of_ay
        from {{ ref("int_powerschool__calendar_week") }} as cw
        where cw.academic_year >= 2025
    ),

    school_id_calendar_mapping as (
        select
            employee_number,
            effective_date_start,
            effective_date_end,
            case
                when
                    home_work_location_powerschool_school_id is null
                    and home_business_unit_name = "KIPP TEAM and Family Schools Inc."
                then 133570965
                when
                    home_work_location_powerschool_school_id = 0
                    and home_business_unit_name = "KIPP TEAM and Family Schools Inc."
                then 133570965
                when
                    home_work_location_powerschool_school_id is null
                    and home_business_unit_name = "TEAM Academy Charter School"
                then 133570965
                when
                    home_work_location_powerschool_school_id = 0
                    and home_business_unit_name = "TEAM Academy Charter School"
                then 133570965
                when
                    home_work_location_powerschool_school_id is null
                    and home_business_unit_name = "KIPP Miami"
                then 30200803
                when
                    home_work_location_powerschool_school_id = 0
                    and home_business_unit_name = "KIPP Miami"
                then 30200803
                when
                    home_work_location_powerschool_school_id is null
                    and home_business_unit_name = "KIPP Cooper Norcross Academy"
                then 179901
                when
                    home_work_location_powerschool_school_id = 0
                    and home_business_unit_name = "KIPP Cooper Norcross Academy"
                then 179901
                else home_work_location_powerschool_school_id
            end as ps_id_for_cal_mapping,
        from {{ ref("int_people__staff_roster_history") }}
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
from {{ ref("int_people__staff_roster_history") }} as srh
inner join
    school_id_calendar_mapping as sicm
    on srh.primary_indicator
    and srh.employee_number = sicm.employee_number
    and srh.effective_date_start = sicm.effective_date_start
    and srh.effective_date_end = sicm.effective_date_end
inner join
    date_spine as ds
    on sicm.ps_id_for_cal_mapping = ds.schoolid
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
    )
