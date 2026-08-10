select
    id,
    name,
    description,
    directmemberscount as direct_members_count,
    admincreated as admin_created,
    etag,
    kind,

    /* repeated */
    aliases,
    noneditablealiases as non_editable_aliases,

    /* Google preserves the case it was given when a group is created, but an
    address is a case-insensitive identifier and the extract joins on a
    lowercase constructed value. Normalizing here keeps that join honest. */
    lower(email) as email,
from {{ source("google_directory", "src_google_directory__groups") }}
