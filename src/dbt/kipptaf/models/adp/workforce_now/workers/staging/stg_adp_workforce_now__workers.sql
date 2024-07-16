with
    -- trunk-ignore(sqlfluff/ST03)
    workers as (
        select
            associateoid as associate_oid,
            _dagster_partition_date as effective_date_start,

            workerid.idvalue as worker_id__id_value,

            workerid.schemecode.effectivedate as worker_id__scheme_code__effective_date,
            workerid.schemecode.codevalue as worker_id__scheme_code__code_value,
            workerid.schemecode.longname as worker_id__scheme_code__long_name,
            workerid.schemecode.shortname as worker_id__scheme_code__short_name,

            workerstatus.statuscode.effectivedate
            as worker_status__status_code__effective_date,
            workerstatus.statuscode.codevalue as worker_status__status_code__code_value,
            workerstatus.statuscode.longname as worker_status__status_code__long_name,
            workerstatus.statuscode.shortname as worker_status__status_code__short_name,

            _languagecode.effectivedate as language_code__effective_date,
            _languagecode.codevalue as language_code__code_value,
            _languagecode.longname as language_code__long_name,
            _languagecode.shortname as language_code__short_name,

            /* objects */
            person,
            customfieldgroup as custom_field_group,
            workassignments as work_assignments,
            businesscommunication as business_communication,
            photos,

            date(workerdates.originalhiredate) as worker_dates__original_hire_date,
            date(workerdates.rehiredate) as worker_dates__rehire_date,
            date(workerdates.terminationdate) as worker_dates__termination_date,

            timestamp_sub(
                timestamp_add(timestamp(_dagster_partition_date), interval 1 day),
                interval 1 millisecond
            ) as effective_date_timestamp,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "to_json_string(workerid)",
                        "to_json_string(workerdates)",
                        "to_json_string(workerstatus)",
                        "to_json_string(_languagecode)",
                        "to_json_string(person)",
                        "to_json_string(customfieldgroup)",
                        "to_json_string(workassignments)",
                        "to_json_string(businesscommunication)",
                        "to_json_string(photos)",
                    ]
                )
            }} as surrogate_key,
        from {{ source("adp_workforce_now", "src_adp_workforce_now__workers") }}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="workers",
                partition_by="associate_oid, surrogate_key",
                order_by="effective_date_start asc",
            )
        }}
    ),

    with_end_date as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            *,

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
    )

select
    *,

    if(
        current_date('{{ var("local_timezone") }}')
        between effective_date_start and effective_date_end,
        true,
        false
    ) as is_current_record,
from with_end_date
