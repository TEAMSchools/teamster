with
    date_spine as (
        select
            date_week,
            {{
                date_to_fiscal_year(
                    date_field="date_week",
                    start_month=7,
                    year_source="start",
                )
            }} as academic_year,
        from
            unnest(
                generate_date_array(
                    {# first date of the appsheet snapshot #}
                    '2023-08-04',
                    {# need current week as it happens #}
                    current_date('{{ var("local_timezone") }}') + 7,
                    interval 1 week
                )
            ) as date_week
    ),

    seats_snapshot as (select *, from {{ ref("int_seat_tracker__snapshot") }}),

    seats_detail as (
        select *, from {{ ref("stg_google_appsheet__seat_tracker__seats") }}
    ),

    projections as (
        select *, from {{ ref("stg_google_sheets__recruitment__school_projections") }}
    ),

    staff_roster as (select *, from {{ ref("int_people__staff_roster") }}),

    final as (
        select
            date_spine.date_week,

            seats_snapshot.staffing_model_id,
            seats_snapshot.staffing_status,
            seats_snapshot.status_detail,
            seats_snapshot.plan_status,
            seats_snapshot.academic_year,
            seats_snapshot.teammate_employee_number,
            seats_snapshot.valid_from,
            seats_snapshot.valid_to,

            seats_detail.adp_dept,
            seats_detail.adp_location,
            seats_detail.adp_title,
            seats_detail.display_name,
            seats_detail.entity,
            seats_detail.grade_band,
            seats_detail.short_name,
            seats_detail.recruitment_group,

            projections.anticipated_hires,

            teammate_info.formatted_name as teammate,

            recruiter_info.formatted_name as recruiter,
            recruiter_info.reports_to_formatted_name as recruiter_manager,

            if(seats_snapshot.is_open, 1, 0) as open_seats,
            if(seats_snapshot.is_new_hire, 1, 0) as new_hires,
            if(seats_snapshot.is_staffed, 1, 0) as staffed_seats,
            if(seats_snapshot.is_active, 1, 0) as active_seats,
            if(seats_snapshot.is_mid_year_hire, 1, 0) as mid_year_hires,
        from date_spine
        inner join
            seats_snapshot
            on date_spine.date_week
            between seats_snapshot.valid_from and seats_snapshot.valid_to
            and date_spine.academic_year <= seats_snapshot.academic_year 
        inner join
            seats_detail
            on seats_snapshot.staffing_model_id = seats_detail.staffing_model_id
            and seats_snapshot.academic_year = seats_detail.academic_year
        left join
            projections
            on seats_detail.adp_location = projections.primary_site
            and seats_detail.academic_year = projections.academic_year
        left join
            staff_roster as teammate_info
            on seats_snapshot.teammate_employee_number = teammate_info.employee_number
        left join
            staff_roster as recruiter_info
            on seats_detail.recruiter = recruiter_info.employee_number
    )

select *,
from final
