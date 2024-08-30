{{- config(severity="warn", store_failures=true, store_failures_as="view") -}}

with
    week_assessment_scaffold as (
        select
            assessment_id,
            title,
            administered_at,
            region,

            avg(if(student_assessment_id is not null, 1, 0)) as pct_completion,
        from {{ ref("int_assessments__scaffold") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and is_internal_assessment
            and not is_replacement
            and administered_at < current_date('{{ var("local_timezone") }}')
        group by all
    )

select *,
from week_assessment_scaffold
where pct_completion < 0.5
