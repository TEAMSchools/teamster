{{ config(enabled=False) }}
select *
from {{ ref("stg_illuminate__agg_student_responses_overall") }}
