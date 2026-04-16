with
    intervention_scaffold as (
        select
            'kippmiami' as region,
            commlog_reason,

            safe_cast(
                regexp_extract(commlog_reason, r'(\d+)') as int
            ) as absence_threshold,
        from
            unnest(
                [
                    'Chronic Absence: 3',
                    'Chronic Absence: 5',
                    'Chronic Absence: 8',
                    'Chronic Absence: 10',
                    'Chronic Absence: 15+'
                ]
            ) as commlog_reason

        union all

        select
            region,
            commlog_reason,

            safe_cast(
                regexp_extract(commlog_reason, r'(\d+)') as int
            ) as absence_threshold,
        from
            unnest(
                [
                    'Chronic Absence: 4',
                    'Chronic Absence: 8',
                    'Chronic Absence: 12',
                    'Chronic Absence: 16',
                    'Chronic Absence: 20',
                    'Chronic Absence: 30',
                    'Chronic Absence: 40'
                ]
            ) as commlog_reason
        cross join unnest(['kippnewark', 'kippcamden']) as region
    )

select
    {{ dbt_utils.generate_surrogate_key(["region", "commlog_reason"]) }}
    as intervention_type_key,

    region,
    commlog_reason,
    absence_threshold,
from intervention_scaffold
