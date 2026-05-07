{{
    config(
        severity="error",
        store_failures=true,
        store_failures_as="view",
        meta={
            "dagster": {
                "ref": {"name": "stg_google_sheets__people__locations"},
            },
        },
    )
}}

/* Returns rows when the canonical-grain location master and the alias
   crosswalk drift apart. Two-direction check:
     - missing_in_master: alias `clean_name` not present as a master
       `location_name`. INNER-join consumers would silently drop these
       aliases; LEFT-join consumers would propagate NULL canonical attrs.
     - missing_in_alias: master `location_name` not present as an alias
       `clean_name`. Aliases are how upstream typed strings (PowerSchool
       school names, ADP location strings, Zendesk slugs) resolve to a
       canonical row, so a master row without aliases is unreachable from
       most upstream lookups. */
with
    alias_clean_names as (
        select distinct clean_name,
        from {{ ref("stg_google_sheets__people__location_crosswalk") }}
        where clean_name is not null
    ),

    master_names as (
        select distinct location_name,
        from {{ ref("stg_google_sheets__people__locations") }}
    )

select 'missing_in_master' as direction, alias.clean_name as `name`,
from alias_clean_names as alias
left join master_names as m on alias.clean_name = m.location_name
where m.location_name is null

union all

select 'missing_in_alias' as direction, m.location_name as `name`,
from master_names as m
left join alias_clean_names as alias on m.location_name = alias.clean_name
where alias.clean_name is null
