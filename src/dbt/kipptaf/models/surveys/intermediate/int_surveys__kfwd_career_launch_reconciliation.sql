with
    raw as (
        select response_id, item_title, text_value, create_timestamp,
        from {{ ref("int_google_forms__form_responses") }}
        where
            form_id = '1oUBls4Kaj0zcbQyeWowe8Es1BFqunolAPEamzT6enQs'
            and item_title
            in ('Survey response ID', 'Salesforce contact ID', 'Reconcile or Exclude?')
    ),

    pivoted as (
        select
            survey_response_id, reconcile_or_exclude, sf_contact_id, create_timestamp,
        from
            raw pivot (
                max(text_value) for item_title in (
                    'Survey response ID' as survey_response_id,
                    'Salesforce contact ID' as sf_contact_id,
                    'Reconcile or Exclude?' as reconcile_or_exclude
                )
            )
    )

select survey_response_id, reconcile_or_exclude, sf_contact_id,
from pivoted
qualify
    row_number() over (partition by survey_response_id order by create_timestamp desc)
    = 1
