select distinct * except (enrollment_type),
from {{ source("finalsite", "status_report") }}
