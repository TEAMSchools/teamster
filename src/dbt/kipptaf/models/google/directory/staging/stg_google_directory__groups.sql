select
    id,
    email,
    name,
    description,
    directmemberscount as direct_members_count,
    admincreated as admin_created,
    etag,
    kind,

    /* repeated */
    aliases,
    noneditablealiases as non_editable_aliases,
from {{ source("google_directory", "src_google_directory__groups") }}
