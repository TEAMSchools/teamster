select * except (date_administered), date(date_administered) as date_administered,
from {{ source("illuminate_dna_repositories", "repositories") }}
