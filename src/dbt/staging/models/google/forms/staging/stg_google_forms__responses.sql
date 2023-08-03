select
    fr._dagster_partition_key as form_id,

    r.responseid as response_id,
    r.createtime as create_time,
    r.lastsubmittedtime as last_submitted_time,
    r.respondentemail as respondent_email,
    r.totalscore as total_score,
    r.answers,

    row_number() over (
        partition by fr._dagster_partition_key, r.respondentemail
        order by r.lastsubmittedtime desc
    ) as rn_form_respondent_submitted_desc
from {{ source("google_forms", "src_google_forms__responses") }} as fr
cross join unnest(responses) as r
