with
    responses as (
        select
            _dagster_partition_key as form_id,
            responseid as response_id,
            createtime as create_time,
            lastsubmittedtime as last_submitted_time,
            respondentemail as respondent_email,
            totalscore as total_score,
            answers,

            timestamp(lastsubmittedtime) as last_submitted_timestamp,
            timestamp(createtime) as create_timestamp,

            row_number() over (
                partition by _dagster_partition_key, respondentemail
                order by lastsubmittedtime desc
            ) as rn_form_respondent_submitted_desc,
        from {{ source("google_forms", "src_google_forms__responses") }}
    )

select
    *,

    date(
        last_submitted_timestamp, '{{ var("local_timezone") }}'
    ) as last_submitted_date_local,
from responses
