with
    seats as (select *, from {{ ref("snapshot_seat_tracker__seats") }}),

    final as (
        select
            academic_year,
            staffing_model_id,
            entity,
            grade_band,
            recruitment_group,
            adp_dept as home_department_name,
            adp_title as job_title,
            adp_location as home_work_location_name,
            short_name as location_short_name,
            recruiter as recruiter_employee_number,
            teammate as teammate_employee_number,
            plan_status,
            staffing_status,
            status_detail,
            mid_year_hire as is_mid_year_hire,
            dbt_valid_from,
            dbt_valid_to,
        from seats
    )

select *,
from final
