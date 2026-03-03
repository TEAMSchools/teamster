select
    enrollment_year_extract,
    enrollment_academic_year,
    enrollment_academic_year_display,
    enrollment_type,
    detailed_status,
    detailed_status_ranking,
    detailed_status_branched_ranking,
    valid_detailed_status,
    fs_status_field,
    qa_flag,

    status_group_name,
    status_group_value,

from
    {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} unpivot (
        status_group_value for status_group_name in (
            status_group_numerator,
            status_group_denominator,
            conversion_metric_numerator_1,
            conversion_metric_numerator_2,
            conversion_metric_numerator_3,
            conversion_metric_denominator
        )
    )
