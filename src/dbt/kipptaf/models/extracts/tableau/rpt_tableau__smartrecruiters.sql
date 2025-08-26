with
    date_spine as (),

    applications as (select *, from {{ ref("stg_smartrecruiters__applications") }}),

    applications_unpivoted as (
        select *, status_type, date_val,
        from
            applications unpivot (
                date_val for status_type in (
                    demo_date,
                    hired_date,
                    new_date,
                    offer_date,
                    phone_screen_complete_date,
                    phone_screen_requested_date
                )
            )
    ),

    final as (
        select
            -- Explicit column listing
            applications_unpivoted.application_id,
            applications_unpivoted.candidate_id,
            {# to do: add columns explicitly #}
            applications_unpivoted.status_type,
            applications_unpivoted.date_val,
            coalesce(
                applications_unpivoted.resume_score, applications_unpivoted.star_score
            ) as resume_score,
            trim(subject_preference) as subject_preference,
            case
                when applications_unpivoted.hired_date is not null then 1 else 0
            end as has_hired_status,
            case
                when applications_unpivoted.offer_date is not null then 1 else 0
            end as has_offer_status,
            case
                when applications_unpivoted.demo_date is not null then 1 else 0
            end as has_demo_status,
            case
                when applications_unpivoted.phone_screen_complete_date is not null
                then 1
                else 0
            end as has_phone_screen_complete_status,
            case
                when applications_unpivoted.phone_screen_requested_date is not null
                then 1
                else 0
            end as has_phone_screen_requested_status,
            case
                when applications_unpivoted.new_date is not null then 1 else 0
            end as has_new_status,
        from applications_unpivoted
        cross join unnest(split(subject_preference, ',')) as subject_preference
    )

select *,
from final
