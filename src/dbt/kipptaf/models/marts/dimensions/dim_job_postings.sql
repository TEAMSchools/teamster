with
    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    postings as (
        select
            job_title,
            department_internal,
            department_org_field_value,
            job_city,
            recruiters,
            new_date,

            row_number() over (
                partition by job_title, department_internal, job_city
                order by new_date desc
            ) as rn_posting,
        from {{ ref("stg_smartrecruiters__applications") }}
    ),

    deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation="postings",
                partition_by="job_title, department_internal, job_city",
                order_by="new_date desc",
            )
        }}
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["job_title", "department_internal", "job_city"]
        )
    }} as job_posting_key,

    job_title,
    department_internal,
    department_org_field_value,
    job_city,
    recruiters,
from deduplicated
