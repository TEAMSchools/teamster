with
    -- trunk-ignore(sqlfluff/ST03): consumed by dbt_utils.deduplicate via Jinja below
    renamed as (
        select
            lc.name,
            lc.abbreviation,
            lc.grade_band,
            lc.region,
            lc.powerschool_school_id,
            lc.deanslist_school_id,
            lc.reporting_school_id,
            lc.is_campus,
            lc.is_pathways,
            lc.dagster_code_location,
            lc.head_of_schools_employee_number,

            lc.clean_name as location_name,

            cc.name as campus_name,
        from
            {{
                source(
                    "google_sheets", "src_google_sheets__people__location_crosswalk"
                )
            }} as lc
        left join
            {{ source("google_sheets", "src_google_sheets__people__campus_crosswalk") }}
            as cc
            on lc.clean_name = cc.location_name
    ),

    -- the source has one row per location alias (raw `name`); collapse aliases
    -- to one canonical row per logical school. crosswalk columns are stable
    -- within a group, so order_by is only a deterministic tie-breaker. pick
    -- alphabetical `name` so the output is stable across runs.
    deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation="renamed",
                partition_by=(
                    "powerschool_school_id, dagster_code_location, "
                    "location_name, is_pathways"
                ),
                order_by="name asc",
            )
        }}
    )

select
    powerschool_school_id,
    dagster_code_location,
    location_name,
    is_pathways,

    abbreviation,
    region,
    grade_band,
    deanslist_school_id,
    reporting_school_id,
    is_campus,
    head_of_schools_employee_number,
    campus_name,
from deduplicated
