select
    i.category as `type`,
    i.location,

    cast(i.incident_id as string) as incident_id,
    cast(i.school_id as string) as school_id,
    cast(i.issue_ts_date as date) as `date`,
from {{ ref("int_deanslist__incidents") }} as i
where
    i._dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
    and i.create_ts_academic_year = {{ var("current_academic_year") }}
    and (
        i.referral_tier is null
        or i.referral_tier not in ('Social Work', 'Non-Behavioral')
    )
    and (i.category is null or i.category not like 'Documentation%')
