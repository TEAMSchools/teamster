with
    source as (
        select *, cast(left(_dagster_partition_key, 4) as int) as file_year,
        from
            {{
                source(
                    "google_sheets", "src_google_sheets__finalsite__status_crosswalk"
                )
            }}
    )

select *, max(file_year) over () as finalsite_current_academic_year,
from source
