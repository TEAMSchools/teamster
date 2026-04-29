select adp_home_work_location_name as location_clean_name, coupa_address_name,
from {{ source("google_sheets", "src_google_sheets__coupa__address_name_crosswalk") }}
