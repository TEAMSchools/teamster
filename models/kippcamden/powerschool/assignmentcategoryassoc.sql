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
            executionid
        from {{ source("kippcamden_powerschool", "src_assignmentcategoryassoc") }}
        {% if is_incremental() %}
        where _file_name = '{{ var("_file_name") }}'
        {% endif %}
    ),

    updates as (
        select *
        from using_clause
        {% if is_incremental() %}
        where
            assignmentcategoryassocid
            in (select assignmentcategoryassocid from {{ this }})
        {% endif %}
    ),

    inserts as (
        select *
        from using_clause
        where
            assignmentcategoryassocid
            not in (select assignmentcategoryassocid from updates)
    )

select *
from updates

union all

select *
from inserts
