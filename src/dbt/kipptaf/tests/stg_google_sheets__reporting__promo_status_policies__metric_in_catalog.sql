with
    catalog as (
        /* grain projection: metric is the partition key; not a mask for upstream
        duplicates */
        select distinct metric,
        from {{ ref("int_students__promotional_status_metrics_unpivot") }}

        union all

        select pseudo_metric as metric,
        from
            unnest(
                ['is_off_track_attendance', 'is_off_track_academic']
            ) as pseudo_metric
    )

select p.academic_year, p.region, p.domain, p.metric,
from {{ ref("stg_google_sheets__reporting__promo_status_policies") }} as p
left join catalog as c on p.metric = c.metric
where c.metric is null
