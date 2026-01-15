select
    *,

    case
        when org_level = 'org'
        then org_level
        when org_level = 'region'
        then region
        when org_level = 'school'
        then cast(schoolid as string)
    end as join_key,
from {{ source("google_sheets", "src_google_sheets__topline__enrollment_targets") }}
