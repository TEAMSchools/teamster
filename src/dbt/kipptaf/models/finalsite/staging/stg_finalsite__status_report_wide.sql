with
    transformation as (
        select
            * except (
                inquiry_completed_date,
                review_in_progress_date,
                accepted_date,
                assigned_school_date,
                campus_transfer_requested_date,
                parent_declined_date,
                not_enrolling_date
            ),

            if(
                grade in ('K', 'Kindergarten'),
                0,
                cast(regexp_extract(grade, r'\d+') as int)
            ) as grade_level,

            safe_cast(inquiry_completed_date as timestamp) as inquiry_completed_date,
            safe_cast(review_in_progress_date as timestamp) as review_in_progress_date,
            safe_cast(accepted_date as timestamp) as accepted_date,
            safe_cast(assigned_school_date as timestamp) as assigned_school_date,
            safe_cast(
                campus_transfer_requested_date as timestamp
            ) as campus_transfer_requested_date,
            safe_cast(parent_declined_date as timestamp) as parent_declined_date,
            safe_cast(not_enrolling_date as timestamp) as not_enrolling_date,

        from {{ ref("stg_google_sheets__finalsite__status_report_wide") }}
    )

select
    t.*,

    {{ var("current_academic_year") }} as current_academic_year,
    {{ var("current_academic_year") + 1 }} as next_academic_year,

from transformation as t
left join
    {{ ref("stg_google_sheets__finalsite__exclude_ids") }} as e
    on t.finalsite_student_id = e.finalsite_student_id
where e.finalsite_student_id is null
