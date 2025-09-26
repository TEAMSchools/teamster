with
    calendar as (select *, from {{ ref("int_powerschool__calendar_week") }}),

    /* only active seats for the current academic year */
    seat_tracker as (
        select *,
        from {{ ref("int_seat_tracker__snapshot") }}
        where academic_year = {{ var("current_academic_year") }} and is_active
    ),

    locations as (select *, from {{ ref("int_people__location_crosswalk") }}),

    final as (
        select
            seat_tracker.staffing_model_id,
            seat_tracker.entity,

            locations.location_powerschool_school_id as schoolid,

            calendar.week_start_monday,
            calendar.week_end_sunday,
            calendar.academic_year,

            if(seat_tracker.is_staffed, 1, 0) as is_staffed,
        from seat_tracker
        left join locations on seat_tracker.adp_location = locations.location_name
        inner join
            calendar
            on locations.location_powerschool_school_id = calendar.schoolid
            and calendar.week_start_monday
            between seat_tracker.valid_from and seat_tracker.valid_to
    )

select
    f.academic_year,
    f.entity,
    f.schoolid,
    f.week_start_monday,

    round(avg(f.is_staffed), 3) as metric_aggregate_value,
from final as f
inner join
    {{ ref("stg_google_sheets__topline_aggregate_goals") }} as g
    on f.entity = g.entity
    and f.schoolid = g.schoolid
group by f.academic_year, f.entity, f.schoolid, f.week_start_monday

union all

select
    f.academic_year,
    f.entity,
    null as schoolid,
    f.week_start_monday,

    round(avg(f.is_staffed), 3) as metric_aggregate_value,
from final as f
inner join
    {{ ref("stg_google_sheets__topline_aggregate_goals") }} as g on f.entity = g.entity
group by f.academic_year, f.entity, f.week_start_monday

union all

select
    f.academic_year,
    'All' as entity,
    null as schoolid,
    f.week_start_monday,

    round(avg(f.is_staffed), 3) as metric_aggregate_value,
from final as f
inner join
    {{ ref("stg_google_sheets__topline_aggregate_goals") }} as g on f.entity = g.entity
group by f.academic_year, f.entity, f.week_start_monday
