-- Focus contact detail titles are free-typed; phone_type maps them to the
-- vocabulary shared with the Finalsite contacts intermediate. Email-shaped
-- titles (e.g. "Home Email") also match the home/work substrings below, so
-- is_email_title is derived here and must be checked by downstream consumers
-- before treating value as a phone number. Unmapped and ambiguous (matching
-- both vocabularies) titles are surfaced by the
-- focus_unmapped_phone_contact_titles test.
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
