with
    base as (
        {% if env_var("DBT_CLOUD_ENVIRONMENT_TYPE", "") in ["dev", "staging"] %}
            select
                employee_number, adp_associate_id, adp_associate_id_legacy, is_active,
            from {{ source("people", "src_people__employee_numbers") }}
            where is_active
        {% elif is_incremental() %}
            with
                workers as (
                    select worker_id__id_value,
                    from {{ ref("stg_adp_workforce_now__workers") }}
                    where is_current_record
                ),

                updates as (
                    select worker_id__id_value,
                    from workers
                    where
                        worker_id__id_value
                        in (select t.adp_associate_id, from {{ this }} as t)
                ),

                inserts as (
                    select
                        worker_id__id_value,

                        row_number() over (order by worker_id__id_value) as rn,
                    from workers
                    where
                        worker_id__id_value
                        not in (select u.worker_id__id_value, from updates as u)
                ),

                men as (
                    select max(employee_number) as max_employee_number, from {{ this }}
                )

            select
                ins.worker_id__id_value as adp_associate_id,

                cast(null as string) as adp_associate_id_legacy,

                men.max_employee_number + ins.rn as employee_number,

                true as is_active,
            from inserts as ins
            cross join men
        {% else %}
            select
                employee_number, adp_associate_id, adp_associate_id_legacy, is_active,
            from
                {{
                    source(
                        "google_sheets",
                        "stg_google_sheets__people__employee_numbers_archive",
                    )
                }}
        {% endif %}
    )

    -- Deduplicate: upstream sources (both the merged `src_people__employee_numbers`
    -- and the Google Sheets archive) can carry row-level duplicates because the
    -- incremental merge key (`adp_associate_id`) is NULL for some records, so the
    -- merge cannot match on re-run and re-inserts identical rows. Order by
    -- `is_active desc` to prefer active mappings, then `adp_associate_id desc`
    -- so a non-null associate_id beats a null one when both exist (descending
    -- order places NULLs last in BigQuery's array_agg) (#3637).
    {{
        dbt_utils.deduplicate(
            relation="base",
            partition_by="employee_number",
            order_by="is_active desc, adp_associate_id desc",
        )
    }}

    -- depends_on: {{ ref('stg_adp_workforce_now__workers') }}
    -- trunk-ignore(sqlfluff/LT05)
    -- depends_on: {{ source("google_sheets", "stg_google_sheets__people__employee_numbers_archive") }}
    -- depends_on: {{ source("people", "src_people__employee_numbers") }}
