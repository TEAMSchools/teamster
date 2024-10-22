{{- config(materialized="view") -}}

select *,
from {{ ref("int_assessments__assessments") }}
