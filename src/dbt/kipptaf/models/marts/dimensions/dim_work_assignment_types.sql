with
    assignments as (
        select
            wa.item_id,
            wa.effective_date_start,
            wa.worker_type_code__code_value,
            wa.worker_type_code__name,
            wa.benefits_eligibility_class__group_code__name,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "wa.worker_type_code__code_value",
                        "wa.benefits_eligibility_class__group_code__name",
                    ]
                )
            }} as attribute_hash,
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
            worker_type_code__code_value as worker_type_code,
            worker_type_code__name as worker_type_name,
            benefits_eligibility_class__group_code__name as benefits_eligibility_class,

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
    as work_assignment_type_key,

    {{ dbt_utils.generate_surrogate_key(["item_id"]) }} as work_assignment_key,

    worker_type_code,
    worker_type_name,
    benefits_eligibility_class,
    effective_date_start,
    effective_date_end,

    if(effective_date_end = '9999-12-31', true, false) as is_current_record,
from change_points
