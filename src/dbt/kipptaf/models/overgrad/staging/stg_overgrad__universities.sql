{{- config(materialized="table") -}}

select *,
from {{ source("overgrad", "src_overgrad__universities") }}
