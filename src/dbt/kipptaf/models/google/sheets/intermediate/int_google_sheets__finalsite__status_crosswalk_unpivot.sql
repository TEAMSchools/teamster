select
    _dagster_partition_key,
    reporting_season,
    enrollment_type,
    detailed_status,
    detailed_status_ranking,
    detailed_status_branched_ranking,
    valid_detailed_status,
    fs_status_field,
    qa_flag,

    status_group_name,
    status_group_value,

    case
        status_group_value
        when 'Inquiries'
        then 1
        when 'Applications'
        then 2
        when 'Offers'
        then 3
        when 'Accepted'
        then 4
        when 'Currently Accepted'
        then 5
        when 'Pending Offers'
        then 6
        when 'Enrollment In Progress'
        then 7
        when 'Enrolled'
        then 8
        else 0
    end as grouped_status_order,

    case
        when
            status_group_value in (
                'Inquiries',
                'Applications',
                'Offers',
                'Assigned School',
                'Accepted',
                'Offers to Accepted',
                'Accepted to Enrolled',
                'Offers to Enrolled'
            )
        then 'Ever'
        else 'Current'
    end as grouped_status_timeframe,

from
    {{ ref("stg_google_sheets__finalsite__status_crosswalk") }} unpivot (
        status_group_value for status_group_name in (
            status_enrollment,
            status_group_numerator,
            status_group_denominator,
            conversion_metric_numerator_1,
            conversion_metric_numerator_2,
            conversion_metric_numerator_3,
            conversion_metric_denominator
        )
    )
