-- Surfaces DeansList categories that rpt_tableau__okrts_behavior would drop
-- silently. See its properties.yml entry for what a hit means. Refs #5062.
--
-- `mapped` mirrors that model's category_type CASE by hand -- re-copy it
-- whenever the CASE changes. Do not add trim() here: the model matches the
-- raw value, so trimming would hide a padded category the model drops.
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

                    -- Logistics and attendance, not behavior.
                    'Back to School Night',
                    'Pick Up',
                    'Transportation Override',

                    -- Positive and restorative, not corrections.
                    'Student Voice and Action',
                    'Courage - Positive',
                    'Voice - Positive',

                    -- These six ARE corrections, excluded on purpose: AY2025
                    -- Newark one-offs the new policy retired, 109 rows, and
                    -- dropped by the previous allowlist too. Revisit if any
                    -- reappears -- the test stays silent while they sit here.
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
