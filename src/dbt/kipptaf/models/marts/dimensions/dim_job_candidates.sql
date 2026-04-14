with
    applications as (
        select
            candidate_id,
            candidate_first_name,
            candidate_last_name,
            candidate_first_and_last_name,
            candidate_email,
            candidate_source,
            candidate_source_type,
            candidate_source_subtype,
            new_date,
        from {{ ref("stg_smartrecruiters__applications") }}
    ),

    deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation="applications",
                partition_by="candidate_id",
                order_by="new_date desc",
            )
        }}
    )

select
    {{ dbt_utils.generate_surrogate_key(["candidate_id"]) }} as job_candidate_key,

    candidate_id,
    candidate_first_name,
    candidate_last_name,
    candidate_first_and_last_name,
    candidate_email,
    candidate_source,
    candidate_source_type,
    candidate_source_subtype,
from deduplicated
