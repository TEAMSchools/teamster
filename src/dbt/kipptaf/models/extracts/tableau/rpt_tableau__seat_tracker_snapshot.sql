with
    date_spine as (
        select date_week,
        from
            unnest(
                generate_date_array(
                    /* first date of the appsheet snapshot */
                    '2023-08-04',
                    current_date('{{ var("local_timezone") }}'),
                    interval 1 week
                )
            ) as date_week
    ),

    seats_snapshot as (select *, from {{ ref("int_seat_tracker__snapshot") }}),

    seats_detail as (select *, from {{ ref("stg_seat_tracker__seats") }}),

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

            teammate_info.formatted_name as teammate,

            recruiter_info.formatted_name as recruiter,
            recruiter_info.reports_to_formatted_name as recruiter_manager,

            if(seats_snapshot.is_open, 1, 0) as snapshot_open,
            if(seats_snapshot.is_new_hire, 1, 0) as snapshot_new_hire,
            if(seats_snapshot.is_staffed, 1, 0) as snapshot_staffed,
            if(seats_snapshot.is_active, 1, 0) as snapshot_active,
            if(seats_snapshot.is_mid_year_hire, 1, 0) as snapshot_mid_year_hire,
            if(
                current_date()
                between seats_snapshot.valid_from and seats_snapshot.valid_to,
                true,
                false
            ) as is_current,

        from date_spine
        left join
            seats_snapshot
            on date_spine.date_week
            between seats_snapshot.valid_from and seats_snapshot.valid_to
        left join
            seats_detail
            on seats_snapshot.staffing_model_id = seats_detail.staffing_model_id
            and seats_snapshot.academic_year = seats_detail.academic_year
        left join
            staff_roster as teammate_info
            on seats_snapshot.teammate_employee_number = teammate_info.employee_number
        left join
            staff_roster as recruiter_info
            on seats_detail.recruiter = recruiter_info.employee_number
    )

select *,
from final
