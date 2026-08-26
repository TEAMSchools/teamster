with
    incidents as (
        select student_school_id, cast(incident_id as string) as incident_id,
        from {{ ref("int_deanslist__incidents") }}
        where
            _dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
            and create_ts_academic_year = {{ var("current_academic_year") }}
            and (
                referral_tier is null
                or referral_tier not in ('Social Work', 'Non-Behavioral')
            )
            and (category is null or category not like 'Documentation%')
    )

select
    incident_id,

    cast(student_school_id as string) as student_id,
    concat(incident_id, '-', cast(student_school_id as string)) as incident_detail_id,
from incidents
