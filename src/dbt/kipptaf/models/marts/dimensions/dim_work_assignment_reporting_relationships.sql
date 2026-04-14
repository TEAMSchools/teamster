with
    reports_to as (
        select
            rt.item_id,
            rt.effective_date_start,
            rt.reports_to_associate_oid,
            rt.reports_to_position_id,
            rt.reports_to_worker_id__id_value,
            rt.reports_to_worker_name__formatted_name,
            rt.reports_to_worker_name__given_name,
            rt.reports_to_worker_name__family_name_1,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "rt.reports_to_associate_oid",
                        "rt.reports_to_position_id",
                    ]
                )
            }} as attribute_hash,
        from
            {{ ref("int_adp_workforce_now__workers__work_assignments__reports_to") }}
            as rt
    ),

    change_detection as (
        select
            *,

            lag(attribute_hash, 1, '') over (
                partition by item_id order by effective_date_start asc
            ) as attribute_hash_lag,
        from reports_to
    ),

    change_points as (
        select
            item_id,
            effective_date_start,
            reports_to_associate_oid as manager_associate_oid,
            reports_to_position_id as manager_position_id,
            reports_to_worker_id__id_value as manager_worker_id,
            reports_to_worker_name__formatted_name as manager_formatted_name,
            reports_to_worker_name__given_name as manager_given_name,
            reports_to_worker_name__family_name_1 as manager_family_name_1,

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
    as work_assignment_reporting_relationship_key,

    {{ dbt_utils.generate_surrogate_key(["item_id"]) }} as work_assignment_key,

    manager_associate_oid,
    manager_position_id,
    manager_worker_id,
    manager_formatted_name,
    manager_given_name,
    manager_family_name_1,
    effective_date_start,
    effective_date_end,

    if(effective_date_end = '9999-12-31', true, false) as is_current_record,
from change_points
