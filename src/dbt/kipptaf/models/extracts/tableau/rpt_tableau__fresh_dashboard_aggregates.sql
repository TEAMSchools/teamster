with
    summary as (
        select
            _dbt_source_relation,
            academic_year,
            academic_year_display,
            enrollment_year,
            region,
            school,
            finalsite_student_id,
            grade_level,
            grade_level_string,
            detailed_status,
            status_start_date,
            days_in_status,

            'KTAF' as org,

            metric_name,
            metric_value,

        from
            {{ ref("int_students__finalsite_student_roster") }} unpivot (
                metric_value for metric_name in (
                    offered_ops,
                    pending_offer_ops,
                    overall_conversion_ops,
                    offers_to_accepted_num,
                    offers_to_accepted_den,
                    accepted_to_enrolled_num,
                    accepted_to_enrolled_den,
                    offers_to_enrolled_num,
                    offers_to_enrolled_den
                )
            )
    ),

    latest_offer_days as (
        select
            _dbt_source_relation,
            academic_year,
            finalsite_student_id,

            1 as pending_offer_ops,

            if(max(days_in_status) <= 4, 1, 0) as pending_offer_less_equal_4,
            if(
                max(days_in_status) between 5 and 10, 1, 0
            ) as pending_offer_between_5_10,
            if(max(days_in_status) > 10, 1, 0) as pending_offer_greater_10,

        from summary
        where metric_name = 'pending_offer_ops' and metric_value = 1
        group by _dbt_source_relation, academic_year, finalsite_student_id
    ),

    offered as (
        select
            _dbt_source_relation,
            academic_year,
            finalsite_student_id,
            metric_value as offered_ops,

        from summary
        where metric_name = 'offered_ops' and metric_value = 1
    ),

    final_offer_tracking as (
        select
            s._dbt_source_relation,
            s.academic_year,
            s.academic_year_display,
            s.enrollment_year,
            s.org,
            s.region,
            s.school,
            s.grade_level_string,
            s.finalsite_student_id,

            coalesce(o.offered_ops, 0) as offered_ops,

            coalesce(l.pending_offer_ops, 0) as pending_offer_ops,
            coalesce(l.pending_offer_less_equal_4, 0) as pending_offer_less_equal_4,
            coalesce(l.pending_offer_between_5_10, 0) as pending_offer_between_5_10,
            coalesce(l.pending_offer_greater_10, 0) as pending_offer_greater_10,

            row_number() over (
                partition by s.academic_year, s.finalsite_student_id
                order by s.status_start_date desc
            ) as rn,

        from summary as s
        left join
            offered as o
            on s.academic_year = o.academic_year
            and s.finalsite_student_id = o.finalsite_student_id
        left join
            latest_offer_days as l
            on s.academic_year = l.academic_year
            and s.finalsite_student_id = l.finalsite_student_id
        qualify rn = 1
    ),

    unpivot_offer_tracking as (
        select
            _dbt_source_relation,
            academic_year,
            academic_year_display,
            enrollment_year,
            org,
            region,
            school,
            grade_level_string,
            finalsite_student_id,

            metric_name,
            metric_value,

        from
            final_offer_tracking unpivot (
                metric_value for metric_name in (
                    offered_ops,
                    pending_offer_ops,
                    pending_offer_less_equal_4,
                    pending_offer_between_5_10,
                    pending_offer_greater_10
                )
            )
    )

select
    _dbt_source_relation,
    academic_year,
    academic_year_display,
    enrollment_year,
    finalsite_student_id,
    metric_name,
    metric_value,

    'Org' as org_level,
    org as org_level_name,

from unpivot_offer_tracking

union all

select
    _dbt_source_relation,
    academic_year,
    academic_year_display,
    enrollment_year,
    finalsite_student_id,
    metric_name,
    metric_value,

    'Region' as org_level,
    coalesce(region, 'No Region Assigned') as org_level_name,

from unpivot_offer_tracking

union all

select
    _dbt_source_relation,
    academic_year,
    academic_year_display,
    enrollment_year,
    finalsite_student_id,
    metric_name,
    metric_value,

    'School' as org_level,
    coalesce(school, 'No School Assigned') as org_level_name,

from unpivot_offer_tracking

union all

select
    _dbt_source_relation,
    academic_year,
    academic_year_display,
    enrollment_year,
    finalsite_student_id,
    metric_name,
    metric_value,

    'Grade' as org_level,
    coalesce(grade_level_string, 'No Grade Assigned') as org_level_name,

from unpivot_offer_tracking
