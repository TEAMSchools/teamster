with
    applications as (
        select
            * except (resume_score, star_score, subject_preference),
            coalesce(resume_score, star_score) as resume_score,
            if(
                subject_preference is null, 'No Preference', subject_preference
            ) as subject_preference,
            case
                when hired_date is not null
                then 6
                when offer_date is not null
                then 5
                when demo_date is not null
                then 4
                when phone_screen_complete_date is not null
                then 3
                when phone_screen_requested_date is not null
                then 2
                when new_date is not null
                then 1
                else 0
            end as max_stage_reached,
        from {{ ref("stg_smartrecruiters__applications") }}
    ),

    applications_status_cascade as (
        select
            *,
            -- Cascading booleans based on max stage reached
            max_stage_reached >= 1 as has_new_status,
            max_stage_reached >= 2 as has_phone_screen_requested_status,
            max_stage_reached >= 3 as has_phone_screen_complete_status,
            max_stage_reached >= 4 as has_demo_status,
            max_stage_reached >= 5 as has_offer_status,
            max_stage_reached >= 6 as has_hired_status,

        from applications
    ),

    applications_unnested as (
        select
            * except (subject_preference),
            trim(subject_preference) as subject_preference,
        from applications_status_cascade
        cross join unnest(split(subject_preference, ',')) as subject_preference
    ),

    final as (
        select
            applications_unnested.*,
            if(
                applications_unnested.application_status in ('New', 'Lead')
                or applications_unnested.resume_score is null,
                true,
                false
            ) as is_not_reviewed,
        from applications_unnested
    )

select *,
from final
