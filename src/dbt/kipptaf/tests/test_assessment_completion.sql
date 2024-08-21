{{- config(severity="warn") -}}

with
    week_scaffold as (
        /* monday thru sunday */
        select
            date_add(date_trunc(date_value, week), interval 1 day) as week_start_date,
            date_add(date_trunc(date_value, week), interval 7 day) as week_end_date,
        from
            unnest(
                generate_date_array(
                    '{{ var("current_academic_year") }}-07-01',
                    '{{ var("current_academic_year") + 1 }}-06-30',
                    interval 1 week
                )
            ) as date_value
    ),

    week_assessment_scaffold as (
        select
            ws.week_end_date,

            a.assessment_id,
            a.title,
            a.administered_at,
            a.region,

            avg(if(a.student_assessment_id is not null, 1, 0)) as pct_completion,
        from week_scaffold as ws
        inner join
            {{ ref("int_assessments__scaffold") }} as a
            on a.administered_at between ws.week_start_date and ws.week_end_date
            and a.is_internal_assessment
            and not a.is_replacement
        where ws.week_end_date <= current_date('{{ var("local_timezone") }}')
        group by all
    )

select *
from week_assessment_scaffold
where pct_completion < 0.5
