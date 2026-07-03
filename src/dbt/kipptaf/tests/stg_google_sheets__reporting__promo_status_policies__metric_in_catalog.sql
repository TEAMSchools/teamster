{{ config(severity="error") }}

{% set all_metrics = (
    promo_status_metric_columns() + promo_status_pseudo_metric_columns()
) %}

select academic_year, region, domain, metric,
from {{ ref("stg_google_sheets__reporting__promo_status_policies") }}
where
    metric not in (
        {% for m in all_metrics %}
            '{{ m }}'{% if not loop.last %},{% endif %}
        {% endfor %}
    )
