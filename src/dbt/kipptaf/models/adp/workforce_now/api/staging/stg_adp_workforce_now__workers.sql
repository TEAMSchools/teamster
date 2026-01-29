with
    workers as (
        select
            associateoid as associate_oid,
            _dagster_partition_date as effective_date_start,

            /* records */
            _languagecode as language_code,
            person,
            workerdates as worker_dates,
            workerid as worker_id,
            workerstatus as worker_status,

            /* repeated records */
            businesscommunication as business_communication,
            customfieldgroup as custom_field_group,
            photos,
            workassignments as work_assignments,

            /* surrogate keys */
            {{ dbt_utils.generate_surrogate_key(["to_json_string(_languagecode)"]) }}
            as language_code_surrogate_key,
            {{ dbt_utils.generate_surrogate_key(["to_json_string(person)"]) }}
            as person_surrogate_key,
            {{ dbt_utils.generate_surrogate_key(["to_json_string(workerdates)"]) }}
            as worker_dates_surrogate_key,
            {{ dbt_utils.generate_surrogate_key(["to_json_string(workerid)"]) }}
            as worker_id_surrogate_key,
            {{ dbt_utils.generate_surrogate_key(["to_json_string(workerstatus)"]) }}
            as worker_status_surrogate_key,
            {{
                dbt_utils.generate_surrogate_key(
                    ["to_json_string(businesscommunication)"]
                )
            }} as business_communication_surrogate_key,
            {{ dbt_utils.generate_surrogate_key(["to_json_string(customfieldgroup)"]) }}
            as custom_field_group_surrogate_key,
            {{ dbt_utils.generate_surrogate_key(["to_json_string(photos)"]) }}
            as photos_surrogate_key,
            {{ dbt_utils.generate_surrogate_key(["to_json_string(workassignments)"]) }}
            as work_assignments_surrogate_key,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "to_json_string(_languagecode)",
                        "to_json_string(workerdates)",
                        "to_json_string(workerid)",
                        "to_json_string(workerstatus)",
                        "to_json_string(businesscommunication)",
                        "to_json_string(customfieldgroup)",
                        "to_json_string(person)",
                        "to_json_string(photos)",
                        "to_json_string(workassignments)",
                    ]
                )
            }} as surrogate_key,
        from {{ source("adp_workforce_now", "src_adp_workforce_now__workers") }}
    ),

    deduplicate as (
        select
            *,

            lag(surrogate_key, 1, '') over (
                partition by associate_oid order by effective_date_start asc
            ) as surrogate_key_lag,
        from workers
    ),

    flattened as (
        select
            associate_oid,
            effective_date_start,
            business_communication_surrogate_key,
            custom_field_group_surrogate_key,
            language_code_surrogate_key,
            person_surrogate_key,
            photos_surrogate_key,
            work_assignments_surrogate_key,
            worker_dates_surrogate_key,
            worker_id_surrogate_key,
            worker_status_surrogate_key,
            surrogate_key,

            /* records */
            language_code,
            person,
            worker_dates,
            worker_id,
            worker_status,

            /* repeated records */
            business_communication,
            custom_field_group,
            photos,
            work_assignments,

            timestamp(
                effective_date_start, '{{ var("local_timezone") }}'
            ) as effective_date_start_timestamp,

            coalesce(
                date_sub(
                    lead(effective_date_start, 1) over (
                        partition by associate_oid order by effective_date_start asc
                    ),
                    interval 1 day
                ),
                '9999-12-31'
            ) as effective_date_end,
        from deduplicate
        where surrogate_key != surrogate_key_lag
    )

select
    *,

    if(
        current_date('{{ var("local_timezone") }}')
        between effective_date_start and effective_date_end,
        true,
        false
    ) as is_current_record,

    if(
        effective_date_end = '9999-12-31',
        timestamp('9999-12-31 23:59:59'),
        timestamp_sub(
            timestamp_add(
                timestamp(effective_date_end, '{{ var("local_timezone") }}'),
                interval 1 day
            ),
            interval 1 millisecond
        )
    ) as effective_date_end_timestamp,
from flattened
