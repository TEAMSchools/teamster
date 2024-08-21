with
    date_array as (
        select
            generate_date_array(
                date '2023-08-04',
                date({{ var("current_fiscal_year") }}, 6, 30),
                interval 1 week
            ) as dates
    ),

    date_spine as (select date_week, from date_array, unnest(dates) as date_week)

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
