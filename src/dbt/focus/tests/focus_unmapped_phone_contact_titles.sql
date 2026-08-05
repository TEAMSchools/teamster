-- stg_focus__people_join_contacts derives phone_type (regex-mapped phone
-- vocabulary) and is_email_title (regex-mapped email vocabulary) from the
-- free-typed Focus contact-detail title. Warn on two cases: (1) a title
-- matching neither vocabulary (phone_type is null and not an email title), so
-- a newly-introduced Focus contact type is surfaced instead of silently
-- dropped from the phone pivot; (2) a title matching BOTH vocabularies
-- (phone_type is not null and is an email title) -- self-contradictory, since
-- the model excludes it as an email title, silently dropping a value that may
-- hold a real phone number. A title matching only one vocabulary is expected
-- and not flagged.
--
-- `is_email_title is not true` / `is true` are null-safe: a null title yields
-- phone_type = null and is_email_title = null, and a plain `not is_email_title`
-- would evaluate to null (silently excluding the row) rather than flagging it.
select title, count(*) as n,
from {{ ref("stg_focus__people_join_contacts") }}
where
    (phone_type is null and is_email_title is not true)
    or (phone_type is not null and is_email_title is true)
group by title
