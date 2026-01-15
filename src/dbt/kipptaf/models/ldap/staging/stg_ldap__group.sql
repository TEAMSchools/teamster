select
    cn,
    distinguishedname as distinguished_name,

    /* repeated */
    member,
from {{ source("ldap", "src_ldap__group") }}
