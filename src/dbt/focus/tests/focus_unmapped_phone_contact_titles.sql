-- Focus contact-detail titles are free-typed; the phone pivot in
-- int_focus__student_contacts maps them by regex, and excludes every
-- email-shaped title (title contains "email") from phone typing entirely.
-- Warn on two cases: (1) a title matching neither the phone vocabulary nor
-- the email vocabulary, so a newly-introduced Focus contact type is
-- surfaced instead of silently dropped from the phone pivot; (2) a title
-- matching BOTH vocabularies (e.g. "Cell/Email") -- self-contradictory,
-- since the model excludes it as an email title, silently dropping a value
-- that may hold a real phone number. A title matching only one vocabulary
-- is expected and not flagged.
with
    -- coalesce makes a null title visible to the classifications below
    -- instead of vanishing (regexp_contains(null, ...) is null), since the
    -- model also drops null-titled rows and would otherwise lose them
    -- silently from this guard.
    titles as (
        select title, coalesce(lower(title), '') as title_lower,
        from {{ ref("stg_focus__people_join_contacts") }}
    ),

    -- classify each title against the phone-type and email vocabularies used
    -- by the model's phone pivot, as plain boolean columns so the final
    -- WHERE filters columns, not function calls.
    classified as (
        select
            title,

            regexp_contains(
                title_lower, r'cell|mobile|home|work|business|office|day'
            ) as is_phone_title,
            regexp_contains(title_lower, r'e-?mail') as is_email_title,
        from titles
    )

select title, count(*) as n,
from classified
where (not is_phone_title and not is_email_title) or (is_phone_title and is_email_title)
group by title
