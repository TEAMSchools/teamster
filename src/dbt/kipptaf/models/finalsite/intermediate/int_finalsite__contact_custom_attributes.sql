-- Finalsite contacts API layer is enabled only in regions with Finalsite
-- ingestion wired (today: KIPP Miami). Add each region's relation here when its
-- api layer is enabled.
{{
    dbt_utils.union_relations(
        relations=[
            source("kippmiami_finalsite", "int_finalsite__contact_custom_attributes"),
        ]
    )
}}
