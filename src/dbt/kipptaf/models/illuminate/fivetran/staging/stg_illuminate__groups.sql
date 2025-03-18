select
    group_id,
    author_id,
    group_name,
    is_link_to_ec,
    is_tag_public,
    creation_time,
    last_modified_time,
    visibility_group,

    regexp_extract(group_name, r'Math|Reading') as nj_intervention_subject,
    safe_cast(
        regexp_extract(group_name, r'Bucket (\d+)') as int
    ) as nj_intervention_tier,
from {{ source("illuminate", "groups") }}
where not _fivetran_deleted
