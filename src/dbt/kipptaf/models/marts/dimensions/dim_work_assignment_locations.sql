with
    assignments as (
        select
            wa.item_id,
            wa.effective_date_start,
            wa.home_work_location__name_code__code_value,
            wa.home_work_location__name_code__name,
            wa.home_work_location__address__line_one,
            wa.home_work_location__address__line_two,
            wa.home_work_location__address__line_three,
            wa.home_work_location__address__city_name,
            wa.home_work_location__address__postal_code,
            wa.home_work_location__address__country_code,
            wa.home_work_location__address__country_subdivision_level_1__code_value,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "wa.home_work_location__name_code__code_value",
                        "wa.home_work_location__address__line_one",
                        "wa.home_work_location__address__city_name",
                        "wa.home_work_location__address__postal_code",
                        "wa.home_work_location__address__country_subdivision_level_1__code_value",
                    ]
                )
            }}
            as attribute_hash,
        from {{ ref("int_adp_workforce_now__workers__work_assignments") }} as wa
    ),

    change_detection as (
        select
            *,

            lag(attribute_hash, 1, '') over (
                partition by item_id order by effective_date_start asc
            ) as attribute_hash_lag,
        from assignments
    ),

    change_points as (
        select
            item_id,
            effective_date_start,
            home_work_location__name_code__code_value as location_code,
            home_work_location__name_code__name as location_name,
            home_work_location__address__line_one as address_line_one,
            home_work_location__address__line_two as address_line_two,
            home_work_location__address__line_three as address_line_three,
            home_work_location__address__city_name as city_name,
            home_work_location__address__postal_code as postal_code,
            home_work_location__address__country_code as country_code,
            home_work_location__address__country_subdivision_level_1__code_value
            as state_code,

            coalesce(
                date_sub(
                    lead(effective_date_start) over (
                        partition by item_id order by effective_date_start asc
                    ),
                    interval 1 day
                ),
                date '9999-12-31'
            ) as effective_date_end,
        from change_detection
        where attribute_hash != attribute_hash_lag
    )

select
    {{ dbt_utils.generate_surrogate_key(["item_id", "effective_date_start"]) }}
    as work_assignment_location_key,

    {{ dbt_utils.generate_surrogate_key(["item_id"]) }} as work_assignment_key,

    location_code,
    location_name,
    address_line_one,
    address_line_two,
    address_line_three,
    city_name,
    postal_code,
    country_code,
    state_code,
    effective_date_start,
    effective_date_end,

    if(effective_date_end = '9999-12-31', true, false) as is_current_record,
from change_points
