with
    parse_partition_key as (
        select
            id,
            session_id,
            contact_id,
            `status`,
            date_started,
            date_submitted,
            response_time,
            survey_data,
            _dagster_partition_key,

            regexp_extract(_dagster_partition_key, r'\d+', 1, 1) as survey_id,
        from {{ source("alchemer", "src_alchemer__survey_response") }}
        where is_test_data = '0' and `status` = 'Complete'
    ),

    with_surrogate_key as (
        select *, concat(survey_id, '_', id) as surrogate_key, from parse_partition_key
    ),

    -- trunk-ignore(sqlfluff/ST03)
    filtered_disqualified as (
        select *,
        from with_surrogate_key
        where
            surrogate_key not in (
                select surrogate_key,
                from {{ ref("stg_alchemer__survey_response_disqualified") }}
            )
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="filtered_disqualified",
                partition_by="survey_id, id",
                order_by="_dagster_partition_key desc",
            )
        }}
<<<<<<< HEAD
    ),

    transformed as (
        select
            session_id,
            status,
            response_time,
            survey_data,

            safe_cast(survey_id as int) as survey_id,
            safe_cast(id as int) as id,
            safe_cast(contact_id as int) as contact_id,

            concat(survey_id, '_', id) as surrogate_key,

            safe_cast(
                left(
                    date_started, length(date_started) - 4
                ) as timestamp format 'YYYY-MM-DD HH24:MI:SS'
                at time zone '{{ var("local_timezone") }}'
            ) as date_started,

            safe_cast(
                left(
                    date_submitted, length(date_submitted) - 4
                ) as timestamp format 'YYYY-MM-DD HH24:MI:SS'
                at time zone '{{ var("local_timezone") }}'
            ) as date_submitted,

        from deduplicate
    )

select *,
from transformed
where
    surrogate_key not in (
        select surrogate_key,
        from {{ ref("stg_alchemer__survey_response_disqualified") }}
    )
    and status = 'Complete'
=======
    )

select
    session_id,
    `status`,
    response_time,
    survey_data,

    safe_cast(survey_id as int) as survey_id,
    safe_cast(id as int) as id,
    safe_cast(contact_id as int) as contact_id,

    safe_cast(
        left(
            date_started, length(date_started) - 4
        ) as timestamp format 'YYYY-MM-DD HH24:MI:SS'
        at time zone '{{ var("local_timezone") }}'
    ) as date_started,

    safe_cast(
        left(
            date_submitted, length(date_submitted) - 4
        ) as timestamp format 'YYYY-MM-DD HH24:MI:SS'
        at time zone '{{ var("local_timezone") }}'
    ) as date_submitted,
from deduplicate
>>>>>>> 3e34f7969a89130b3f37d5f89fdfb788008d8e77
