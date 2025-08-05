select
    ous.kind as `kind`,
    ous.name as `name`,
    ous.description as `description`,
    ous.etag as `etag`,
    ous.blockinheritance as `block_inheritance`,
    ous.orgunitid as `org_unit_id`,
    ous.orgunitpath as `org_unit_path`,
    ous.parentorgunitid as `parent_org_unit_id`,
    ous.parentorgunitpath as `parent_org_unit_path`,
from {{ source("google_directory", "src_google_directory__orgunits") }} as o
cross join unnest(o.organizationunits) as ous
