{{
    config(
        severity="warn",
        meta={
            "dagster": {
                "ref": {"name": "stg_deanslist__incidents", "package": "deanslist"}
            }
        },
    )
}}

-- reads the raw source: the models null these dates, so a test on them never fails
with
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=source("deanslist", "src_deanslist__incidents"),
                partition_by="incidentid",
                order_by="_file_name desc",
            )
        }}
    ),

    dates as (
        select
            'close_ts_date' as field_name,

            safe_cast(nullif(incidentid, '') as int) as incident_id,
            safe_cast(nullif(closets.date, '') as datetime) as field_value,
        from deduplicate
        where isactive

        union all

        select
            'start_date' as field_name,

            safe_cast(nullif(i.incidentid, '') as int) as incident_id,
            safe_cast(nullif(p.startdate, '') as datetime) as field_value,
        from deduplicate as i
        cross join unnest(i.penalties) as p
        where i.isactive

        union all

        select
            'end_date' as field_name,

            safe_cast(nullif(i.incidentid, '') as int) as incident_id,
            safe_cast(nullif(p.enddate, '') as datetime) as field_value,
        from deduplicate as i
        cross join unnest(i.penalties) as p
        where i.isactive
    )

select incident_id, field_name, field_value,
from dates
where field_value < '{{ var("deanslist_min_valid_date") }}'
