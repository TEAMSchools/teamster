select
    i.category as `type`,
    i.location,

    dd.date_key as `date`,

    cast(i.incident_id as string) as incident_id,

    cast(loc.powerschool_school_id as string) as school_id,
from {{ ref("int_students__behavioral_incidents") }} as i
inner join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on i.location_key = loc.location_key
-- year filter keys on the issue date, not the DeansList create date, so a
-- June incident logged in July stays in June's school year
inner join {{ ref("dim_dates") }} as dd on cast(i.issue_ts_date as date) = dd.date_key
where
    i._dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
    and i.is_active
    and dd.is_current_academic_year
    -- uncategorized incidents stay in the feed, as before the package flag
    and (i.is_behavioral_referral or i.category is null)
