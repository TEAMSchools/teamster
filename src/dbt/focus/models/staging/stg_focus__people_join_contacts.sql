select
    id,
    person_id,
    detail_priority,
    title,
    imported,
    unlisted,
    callout,
    blocked,
    sms,
    unsubscribe,
    uuid,
    created_at,
    updated_at,

    nullif(trim(value), '') as `value`,
    regexp_contains(lower(title), r'e-?mail') as is_email_title,

    case
        when regexp_contains(lower(title), r'cell|mobile')
        then 'mobile'
        when regexp_contains(lower(title), r'home')
        then 'home'
        when regexp_contains(lower(title), r'work|business|office')
        then 'work'
        when regexp_contains(lower(title), r'day')
        then 'daytime'
    end as phone_type,
from {{ source("focus", "people_join_contacts") }}
