with
    combined_snapshot as (
        select
            staffing_model_id,
            staffing_status,
            status_detail,
            mid_year_hire as is_mid_year_hire,
            plan_status,
            cast(academic_year as string) as academic_year,
            cast(dbt_valid_from as date) as valid_from,
            cast(dbt_valid_to as date) as valid_to,
            cast(teammate as string) as teammate,
            if(staffing_status = 'Open', true, false) as is_open,
            if(staffing_status = 'Staffed', true, false) as is_staffed,
            if(plan_status in ('Active', 'TRUE'), true, false) as is_active,
            if(
                status_detail in ('New Hire', 'Transfer In'), true, false
            ) as is_new_hire,
        from {{ ref("snapshot__seat_tracker__seats") }}
        /* last day of manual snapshot from appsheet*/
        where dbt_updated_at > ('2024-08-07')

        union all

        select
            staffing_model_id,
            staffing_status,
            status_detail,
            is_mid_year_hire,
            plan_status,
            academic_year,
            valid_from,
            null as valid_to,
            teammate,
            is_open,
            is_staffed,
            is_active,
            is_new_hire,
        from {{ ref("stg_seat_tracker__log_archive") }}
    ),

    ordered_snapshot as (
        select
            *,
            row_number() over (
                partition by staffing_model_id order by valid_from desc
            ) as rn_valid_from,
        from combined_snapshot
    )

select
    os1.staffing_model_id,
    os1.staffing_status,
    os1.status_detail,
    os1.is_mid_year_hire,
    os1.plan_status,
    os1.academic_year,
    os1.teammate,
    os1.is_open,
    os1.is_staffed,
    os1.is_active,
    os1.is_new_hire,
    os1.valid_from,
    if(
        coalesce(os1.valid_to, os2.valid_from - 1) is null,
        date({{ var("current_fiscal_year") }}, 6, 30),
        coalesce(os1.valid_to, os2.valid_from - 1)
    ) as valid_to,
from ordered_snapshot as os1
left join
    ordered_snapshot as os2
    on os1.staffing_model_id = os2.staffing_model_id
    and os1.rn_valid_from - 1 = os2.rn_valid_from
