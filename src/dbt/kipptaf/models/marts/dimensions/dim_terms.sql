with
    terms as (select *, from {{ ref("stg_google_sheets__reporting__terms") }}),

    /* exclude school_id = 0 sentinel rows (admin/campus pseudo-locations) so */
    /* school-level joins resolve to at most one physical school per region */
    locations_lookup as (
        select powerschool_school_id, location_name, region,
        from {{ ref("stg_people__locations") }}
        where powerschool_school_id <> 0
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "t.`type`",
                "t.code",
                "t.`name`",
                "t.`start_date`",
                "t.region",
                "t.school_id",
            ]
        )
    }} as term_key,

    if(
        t.city is not null,
        {{ dbt_utils.generate_surrogate_key(["t.city"]) }},
        cast(null as string)
    ) as region_key,

    if(
        ll.location_name is not null,
        {{ dbt_utils.generate_surrogate_key(["ll.location_name"]) }},
        cast(null as string)
    ) as location_key,

    t.`type`,
    t.code as term_code,
    t.`name` as term_name,
    t.`start_date`,
    t.end_date,
    t.academic_year,
    t.fiscal_year,
    t.grade_band,
    t.lockbox_date as data_freeze_date,
    t.is_current,
from terms as t
left join
    locations_lookup as ll
    on t.school_id = ll.powerschool_school_id
    and t.city = ll.region
