{{ config(materialized="ephemeral") }}

select *,
from {{ ref("int_powerschool__gpa_term") }}
where is_current
