-- rpt_tableau__okrts_behavior derives category_type from a `case` over
-- behavior_category and then filters `where category_type is not null`,
-- closing the old silent-NULL hole (a category matching no branch used to
-- reach the extract as an invisible NULL, still fanning out the spine
-- columns). That filter opens a new failure of the same shape: a category
-- that matches neither the `case` nor the exclusion list below is now
-- dropped from the extract entirely, with nothing failing and nothing
-- visible on the dashboard -- the same failure class as the incident this
-- branch exists to fix (a taxonomy changed, a hardcoded allowlist did not,
-- and the OKRTS Dashboard silently showed zero corrective behaviors for
-- weeks).
--
-- `mapped` is copied verbatim from the `category_type` CASE in
-- rpt_tableau__okrts_behavior.sql. Nothing mechanically ties the two
-- together -- this is a human transcription kept in sync by convention, not
-- by construction, the same manual-sync risk the taxonomy incident exists to
-- close, one layer removed. Re-copy it whenever that CASE changes.
--
-- `excluded` lists categories that are deliberately kept out of the OKRTS
-- extract -- known and intentional, not oversights (school-specific
-- compliance sweeps, operational/system noise, and deductions/bonuses
-- tracked outside the behavior taxonomy).
--
-- Matching is on the raw category, unmodified, because the model's
-- category_type CASE also matches raw -- an untrimmed `=` / `in (...)`
-- against b.behavior_category. Trimming here would make the guard blind to
-- the exact failure it exists to catch: a padded value would match this
-- test's trimmed comparison and stay silent while the model's untrimmed CASE
-- matches nothing and silently drops it.
with
    behavior as (
        select b.behavior_category,
        from {{ ref("stg_deanslist__behavior") }} as b
        where b.behavior_date >= '{{ var("current_academic_year") - 1 }}-07-01'
    ),

    mapped as (
        select category,
        from
            unnest(
                [
                    'Written Reminders',
                    'Big Reminders',
                    'Accountability (Empowerment)',
                    'Accountability (Purpose, Courage)',
                    'Be Kind (Love)',
                    'Be Kind (Revolutionary Love)',
                    'Effort (Perseverance)',
                    'Effort (Pride)',
                    'Teamwork (Community)',
                    'Corrective Behaviors',
                    'Tier 1 - Corrective Behaviors',
                    'Tier 1 - Habits of Excellence Corrections',
                    'Values',
                    'Values (5)',
                    'Values (10 Point Bonus)'
                ]
            ) as category
    ),

    excluded as (
        select category,
        from
            unnest(
                [
                    'Uniform',
                    'Dress Code',
                    'System Behaviors',
                    'Reflection Period',
                    'Referral Behaviors',
                    'Earned Incentives',
                    'Community Service',
                    'Community Service Hours',
                    'Consequences',
                    'Consequences (for Courage Report only)',
                    'Suspension-worthy Behaviors',
                    'Hall Pass',
                    'Homework',
                    'IEP Breaks',
                    'Busing',
                    'Before Care',
                    'Early / Late Pick Up',
                    'Early / Late Pickup',
                    'Attendance',
                    'Class Attendance',
                    '3.0 GPA Bonus',
                    'Deduction -1',
                    'Deduction -5',
                    'Deduction -10',
                    'Deduction -50',
                    'Big Reminders(SY23)',

                    -- Group 1: non-behavioral logistics and attendance.
                    'Back to School Night',
                    'Pick Up',
                    'Transportation Override',

                    -- Group 2: positive and restorative, not corrections.
                    'Student Voice and Action',
                    'Courage - Positive',
                    'Voice - Positive',

                    -- Group 3: genuinely corrective, excluded deliberately --
                    -- not because they are non-behavioral. Behaviors logged
                    -- under these six include Fighting, Disrespect to
                    -- Teacher, Cell Phone Violation, and Classroom removal.
                    -- Triaged 2026-08-29: AY2025-only one-off taxonomies
                    -- local to Newark schools, 109 rows total against
                    -- 159,609 mapped Corrective rows (0.07%), absent from
                    -- AY2026 because the new culture policy retired them, and
                    -- dropped by the previous allowlist too -- so excluding
                    -- them here is not a regression. They age out of this
                    -- test's own window on their own once
                    -- current_academic_year rolls to 2027 (the window looks
                    -- back only to current_academic_year - 1). If any of the
                    -- six reappears in AY2026, revisit this exclusion -- the
                    -- test will not warn about them while they sit on this
                    -- list.
                    'Courage - Negative',
                    'Confidence - Negative',
                    'Voice - Negative',
                    'Kindness - Negative',
                    'Negative (5th Grade)',
                    'Routines and Systems'
                ]
            ) as category
    )

select b.behavior_category, count(*) as n,
from behavior as b
left join mapped as m on b.behavior_category = m.category
left join excluded as x on b.behavior_category = x.category
where m.category is null and x.category is null
group by b.behavior_category
