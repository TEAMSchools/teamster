-- Focus contact-detail titles are free-typed; the phone pivot in
-- int_focus__student_contacts maps them by regex. Warn on any title that maps
-- to no phone type so a new contact type is surfaced, not silently dropped.
-- Email-shaped titles are expected to be unmapped and are excluded.
select title, count(*) as n,
from {{ ref("stg_focus__people_join_contacts") }}
where
    not regexp_contains(lower(title), r'cell|mobile|home|work|business|office|day')
    and not regexp_contains(lower(title), r'e-?mail')
group by title
