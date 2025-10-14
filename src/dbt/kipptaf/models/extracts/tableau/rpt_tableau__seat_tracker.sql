with

    seats_detail as (select *, from {{ ref("stg_seat_tracker__seats") }}),

    projections as (
        select *, from {{ ref("stg_google_sheets__recruitment__school_projections") }}
    ),

    staff_roster as (select *, from {{ ref("int_people__staff_roster") }}),

    final as (
        select
            seats_detail.*,

            projections.anticipated_hires,

            teammate_info.formatted_name as teammate_name,

            recruiter_info.formatted_name as recruiter_name,
            recruiter_info.reports_to_formatted_name as recruiter_manager,

            if(seats_detail.staffing_status = 'Open', 1, 0) as open_seats,
            if(
                seats_detail.status_detail in ('New Hire', 'Transfer In'), 1, 0
            ) as new_hires,
            if(seats_detail.staffing_status = 'Staffed', 1, 0) as staffed_seats,
            if(seats_detail.plan_status in ('Active', 'TRUE'), 1, 0) as active_seats,
            if(seats_detail.mid_year_hire, 1, 0) as mid_year_hires,
        from seats_detail
        left join
            projections
            on seats_detail.adp_location = projections.primary_site
            and seats_detail.academic_year = projections.academic_year
        left join
            staff_roster as teammate_info
            on seats_detail.teammate = teammate_info.employee_number
        left join
            staff_roster as recruiter_info
            on seats_detail.recruiter = recruiter_info.employee_number
    )

select *,
from final
