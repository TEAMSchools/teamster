with
    date_spine as (
        {%- set end_date = (
            "cast('" + var("current_fiscal_year")
            | string + "-06-30' as date)"
        ) -%}

        {{-
            dbt_utils.date_spine(
                start_date="cast('2023-08-04' as date)",
                end_date=end_date,
                datepart="week",
            )
        -}}

    )

select
    ds.date_week,
    ts.staffing_model_id,
    ts.staffing_status,
    ts.status_detail,
    ts.plan_status,
    ts.academic_year,
    ts.teammate,
    ts.valid_from,
    ts.valid_to,
    if(ts.is_open, 1, 0) as snapshot_open,
    if(ts.is_new_hire, 1, 0) as snapshot_new_hire,
    if(ts.is_staffed, 1, 0) as snapshot_staffed,
    if(ts.is_active, 1, 0) as snapshot_active,
    if(ts.is_mid_year_hire, 1, 0) as snapshot_mid_year_hire,

from date_spine as ds
left join
    {{ ref("int_seat_tracker_snapshot") }} as ts
    on ds.date_week between ts.valid_from and ts.valid_to
