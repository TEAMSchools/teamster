with
    intervention_scaffold as (
        select
            'kippmiami' as _dbt_source_project,
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
            _dbt_source_project,
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
        cross join unnest(['kippnewark', 'kippcamden']) as _dbt_source_project
    ),

    with_business_unit as (
        select
            *,

            case
                _dbt_source_project
                when 'kippnewark'
                then 'TEAM'
                when 'kippcamden'
                then 'KCNA'
                when 'kippmiami'
                then 'KIPP_MIAMI'
                when 'kipppaterson'
                then 'KPAT'
                else 'KIPP_TAF'
            end as business_unit_code,
        from intervention_scaffold
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            ["_dbt_source_project", "family_communication_reason"]
        )
    }} as intervention_type_key,

    {{ dbt_utils.generate_surrogate_key(["business_unit_code"]) }} as region_key,

    family_communication_reason,
    absence_threshold,
from with_business_unit
