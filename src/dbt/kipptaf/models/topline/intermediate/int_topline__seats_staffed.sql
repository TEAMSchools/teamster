with
    calendar as (select *, from {{ ref("int_powerschool__calendar_week") }}),

    {# only active seats for the current academic year #}
    seat_tracker as (
        select *,
        from {{ ref("int_seat_tracker__snapshot") }}
        where
            cast(academic_year as int) = {{ var("current_academic_year") }}
            and is_active
    ),

    locations as (select *, from {{ ref("int_people__location_crosswalk") }}),

    final as (
        select
            seat_tracker.staffing_model_id,
            seat_tracker.entity,
            locations.location_powerschool_school_id as school_id,
            calendar.week_start_monday,
            calendar.week_end_sunday,
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
    staffing_model_id,
    entity,
    school_id,
    week_start_monday,
    week_end_sunday,
    is_staffed,
from final
