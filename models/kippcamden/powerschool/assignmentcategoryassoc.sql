{%- set unique_key = "assignmentcategoryassocid" -%}

{{
    config(
        materialized="incremental",
        incremental_strategy="merge",
        unique_key=unique_key,
    )
}}

{%- set source_name = config.get("schema") -%}
{%- set table_name = "src_" + this.name -%}
{%- set star = dbt_utils.star(
    from=source(source_name, table_name),
    except=["dt"],
) -%}

with
    using_clause as (
        select
            _file_name,
            /* column transformations */
            assignmentcategoryassocid.int_value as assignmentcategoryassocid,
            assignmentsectionid.int_value as assignmentsectionid,
            teachercategoryid.int_value as teachercategoryid,
            yearid.int_value as yearid,
            isprimary.int_value as isprimary,
            whomodifiedid.int_value as whomodifiedid,
            /* exclude transformed columns */
            {{
                dbt_utils.star(
                    from=source(source_name, table_name),
                    except=[
                        "dt",
                        "assignmentcategoryassocid",
                        "assignmentsectionid",
                        "teachercategoryid",
                        "yearid",
                        "isprimary",
                        "whomodifiedid",
                    ],
                )
            }},
        from {{ source(source_name, table_name) }}
        {% if is_incremental() %}
        where
            _file_name
            = 'gs://teamster-{{ var("code_location") }}'
            + '/dagster/{{ var("code_location") }}'
            + '/powerschool/{{ this.identifier }}'
            + '/{{ var("_file_name") }}'
        {% endif %}
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="using_clause",
                partition_by=unique_key,
                order_by="_file_name desc",
            )
        }}
    ),

    updates as (
        select *
        from deduplicate
        {% if is_incremental() %}
        where {{ unique_key }} in (select {{ unique_key }} from {{ this }})
        {% endif %}
    ),

    inserts as (
        select *
        from deduplicate
        where {{ unique_key }} not in (select {{ unique_key }} from updates)
    )

select {{ star }}
from updates

union all

select {{ star }}
from inserts
