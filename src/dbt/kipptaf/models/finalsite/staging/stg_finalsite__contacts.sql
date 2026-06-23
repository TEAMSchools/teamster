-- Finalsite contacts API layer is enabled only in regions with Finalsite
-- ingestion wired (today: KIPP Miami). Add each region's relation here when its
-- api layer is enabled.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippmiami_finalsite", "stg_finalsite__contacts"),
                ]
            )
        }}
    )

select *, {{ extract_code_location("union_relations") }} as _dbt_source_project,
from union_relations
