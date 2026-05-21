{{
    config(
        severity="error",
        store_failures=true,
        store_failures_as="view",
        meta={
            "dagster": {
                "ref": {"name": "dim_regions"},
            },
        },
    )
}}

/* Asserts dim_regions has every business_unit_code that downstream FKs
   target. dim_regions is derived from
   int_adp_workforce_now__workers__work_assignments__organizational_units__pivot
   filtered to business_unit_code is not null — if ADP stops emitting a
   code that location/staff models still hash on, the chain orphans
   silently. This test fires before that happens. */
with
    expected as (
        select bu_code,
        from unnest(['TEAM', 'KCNA', 'KIPP_MIAMI', 'KPAT', 'KIPP_TAF']) as bu_code
    )

select e.bu_code,
from expected as e
left join {{ ref("dim_regions") }} as r on e.bu_code = r.business_unit_code
where r.business_unit_code is null
