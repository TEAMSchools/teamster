with reporting_dates as (

select start_date, end_date
from {{ ref('stg_reporting__terms') }}
where type = 'REC'
   


select
    ts.staffing_model_id,
    ts.valid_from,
    ts.valid_to,
    ts.staffing_status,
    ts.status_detail,
    ts.plan_status,
    ts.academic_year,
    ts.teammate,
    if(ts.is_open, 1, 0) as snapshot_open,
    if(ts.is_new_hire, 1, 0) as snapshot_new_hire,
    if(ts.is_staffed, 1, 0) as snapshot_staffed,
    if(ts.is_active, 1, 0) as snapshot_active,
    if(ts.is_mid_year_hire, 1, 0) as snapshot_mid_year_hire,

from {{ ref("int_seat_tracker_snapshot") }} as ts
