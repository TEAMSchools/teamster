with
    temp_deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation=ref("int_finalsite__status_report"),
                partition_by="surrogate_key",
                order_by="effective_date",
            )
        }}
    )

select
    t.*,

    x.overall_status,
    x.funnel_status,
    x.status_category,
    x.detailed_status_ranking,
    x.powerschool_enroll_status,
    x.valid_detailed_status,
    x.offered,
    x.conversion,
    x.offered_ops,
    x.conversion_ops,

from temp_deduplicate as t
left join
    {{ ref("stg_google_sheets__finalsite_status_crosswalk") }} as x
    -- fix this later when int view is fixed
    on t.academic_year = x.enrollment_academic_year
    and t.enrollment_type = x.enrollment_type
    and t.detailed_status = x.detailed_status
