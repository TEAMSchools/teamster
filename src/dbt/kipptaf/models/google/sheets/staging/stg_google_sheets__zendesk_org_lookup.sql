select
    adp_business_unit,
    zendesk_organization,
    zendesk_secondary_location,

    adp_location as location_clean_name,
from {{ source("google_sheets", "src_google_sheets__zendesk__org_lookup") }}
