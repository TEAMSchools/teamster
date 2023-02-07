{{
    config(
        materialized="incremental",
        incremental_strategy="merge",
        unique_key="assignmentcategoryassocid",
    )
}}

with
    using_clause as (
        select
            assignmentcategoryassocid.int_value as assignmentcategoryassocid,
            assignmentsectionid.int_value as assignmentsectionid,
            teachercategoryid.int_value as teachercategoryid,
            yearid.int_value as yearid,
            isprimary.int_value as isprimary,
            whocreated,
            whencreated,
            whomodified,
            whenmodified,
            ip_address,
            whomodifiedid.int_value as whomodifiedid,
            whomodifiedtype,
            transaction_date,
            executionid,
            row_number() over (
                partition by assignmentcategoryassocid.int_value
                order by _file_name desc
            ) as rn,
        from {{ source("kippcamden_powerschool", "src_assignmentcategoryassoc") }}
        {% if is_incremental() %}
        where
            _file_name
            = 'gs://teamster-{{ var("code_location") }}/dagster/{{ var("code_location") }}/powerschool/assignmentcategoryassoc/{{ var("_file_name") }}'
        {% endif %}
    ),

    updates as (
        select
            assignmentcategoryassocid,
            assignmentsectionid,
            teachercategoryid,
            yearid,
            isprimary,
            whocreated,
            whencreated,
            whomodified,
            whenmodified,
            ip_address,
            whomodifiedid,
            whomodifiedtype,
            transaction_date,
            executionid,
        from using_clause
        where
            rn = 1
            {% if is_incremental() %}
            and assignmentcategoryassocid
            in (select assignmentcategoryassocid from {{ this }})
            {% endif %}
    ),

    inserts as (
        select
            assignmentcategoryassocid,
            assignmentsectionid,
            teachercategoryid,
            yearid,
            isprimary,
            whocreated,
            whencreated,
            whomodified,
            whenmodified,
            ip_address,
            whomodifiedid,
            whomodifiedtype,
            transaction_date,
            executionid,
        from using_clause
        where
            rn = 1
            and assignmentcategoryassocid
            not in (select assignmentcategoryassocid from updates)
    )

select *
from updates

union all

select *
from inserts
