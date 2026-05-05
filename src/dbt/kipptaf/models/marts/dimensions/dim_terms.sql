with
    terms as (select * from {{ ref("stg_google_sheets__reporting__terms") }}),

    code_locations as (
        {{
            dbt_utils.deduplicate(
                relation=ref("stg_google_sheets__people__locations"),
                partition_by="city",
                order_by="(dagster_code_location = 'kipptaf') asc, powerschool_school_id desc",
            )
        }}
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

    sch.location_key,

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
left join code_locations as cl on cl.city = t.city
left join
    {{ ref("stg_powerschool__schools") }} as sch
    on t.school_id = sch.school_number
    and t.school_id <> 0
    and sch._dbt_source_project = cl.dagster_code_location
