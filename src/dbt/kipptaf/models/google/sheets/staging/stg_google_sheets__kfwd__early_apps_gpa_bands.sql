select gpa_band, band_sort, min_gpa, summary_group,
from {{ source("google_sheets", "src_google_sheets__kfwd__early_apps_gpa_bands") }}
where gpa_band is not null
