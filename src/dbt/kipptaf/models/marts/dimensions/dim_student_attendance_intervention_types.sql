with
    intervention_scaffold as (
        select
            'Miami' as region_name,
            family_communication_reason,

            safe_cast(
                regexp_extract(family_communication_reason, r'(\d+)') as int
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
            ) as family_communication_reason

        union all

        select
            region_name,
            family_communication_reason,

            safe_cast(
                regexp_extract(family_communication_reason, r'(\d+)') as int
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
            ) as family_communication_reason
        cross join unnest(['Newark', 'Camden']) as region_name
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["region_name", "family_communication_reason"]
        )
    }} as intervention_type_key,

    {{ dbt_utils.generate_surrogate_key(["region_name"]) }} as region_key,

    family_communication_reason,
    absence_threshold,
from intervention_scaffold
