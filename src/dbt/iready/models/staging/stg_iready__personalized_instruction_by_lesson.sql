{% set src_model = source("iready", "src_iready__personalized_instruction_by_lesson") %}

select
    {{ dbt_utils.star(from=src_model, except=["completion_date"]) }},

    safe_cast(completion_date as date) as completion_date,
    safe_cast(left(academic_year, 4) as int) as academic_year_int,
    if(passed_or_not_passed = 'Passed', 1.0, 0.0) as passed_or_not_passed_numeric,
from {{ src_model }}
