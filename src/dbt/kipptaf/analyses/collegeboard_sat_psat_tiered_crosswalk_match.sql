-- SAT/PSAT Tiered Crosswalk Match
--
-- SAT and PSAT College Board IDs are a different ID space from AP IDs, so they
-- resolve through their own crosswalk tab (src_collegeboard__sat_id_crosswalk).
-- A gap is any cb_id in either staging model with no crosswalk row.
--
-- Tiers:
-- S   - secondary_id equals a PowerSchool student_number AND the DOB agrees.
-- Schools enter the local id in secondary_id, and on 2026-09-24 it
-- agreed with the crosswalk on 1,616 of 1,624 SAT rows and 2,666 of
-- 2,683 PSAT rows. The DOB check guards the disagreeing remainder;
-- an id match whose DOB disagrees goes to flagged_for_review.
-- A/B - exact DOB + last_name (raw, or diacritic-stripped on both sides)
-- C   - exact DOB + shared last_name TOKEN (split on hyphen/space)
-- D   - DOB exactly 365/366 days apart AND both first_name and last_name
-- match exactly
-- Tiebreak - when the name tiers yield >1 distinct student_number for a gap,
-- narrow using first_name (case-fold, diacritic-strip, alphanumeric only).
--
-- Tier C/D gender check is a HARD GATE (mismatch -> flagged_for_review).
-- Unlike the AP match, PowerSchool rows are not scoped to a year: SAT files
-- carry no enrollment year, and DOB + last name is already tight network-wide.
--
-- No fuzzy/similarity matching anywhere -- every transform is deterministic.
--
-- Validation mode: --vars '{sat_psat_match_all_ids: true}' treats every cb_id as
-- a gap, so the output can be scored against the existing crosswalk.
{% set all_ids = var("sat_psat_match_all_ids", false) %}
with
    cb as (
        select
            'SAT' as test,
            cb_id,
            name_first,
            name_last,
            birth_date,
            gender,

            safe_cast(secondary_id as int64) as secondary_id,
        from {{ ref("stg_collegeboard__sat") }}

        union all

        select
            'PSAT' as test,
            cb_id,
            name_first,
            name_last,
            birth_date,
            gender,
            secondary_id,
        from {{ ref("stg_collegeboard__psat") }}
    ),

    -- grain projection, not dup-masking: one identity per test + cb_id
    gaps as (
        select distinct
            cb.test,
            cb.cb_id,
            cb.name_first as cb_first_name,
            cb.name_last as cb_last_name,
            cb.birth_date as cb_dob,
            cb.gender as cb_gender,
            cb.secondary_id,
        from cb
        left join
            {{ ref("stg_google_sheets__collegeboard__sat_id_crosswalk") }} as xw
            on cb.cb_id = xw.college_board_id
        {% if not all_ids %} where xw.college_board_id is null {% endif %}
    ),

    -- grain projection, not dup-masking: one identity per student_number
    ps as (
        select distinct
            student_number,
            first_name,
            last_name,
            dob,
            gender,

            regexp_replace(
                normalize(upper(last_name), nfd), r'\pM', ''
            ) as last_name_stripped,
            regexp_replace(
                regexp_replace(normalize(upper(first_name), nfd), r'\pM', ''),
                r'[^A-Z0-9]',
                ''
            ) as first_name_norm,
            split(
                regexp_replace(
                    regexp_replace(normalize(upper(last_name), nfd), r'\pM', ''),
                    '-',
                    ' '
                ),
                ' '
            ) as last_name_tok,
        from {{ ref("base_powerschool__student_enrollments") }}
    ),

    gaps_norm as (
        select
            *,

            regexp_replace(
                normalize(upper(cb_last_name), nfd), r'\pM', ''
            ) as cb_last_name_stripped,
            regexp_replace(
                regexp_replace(normalize(upper(cb_first_name), nfd), r'\pM', ''),
                r'[^A-Z0-9]',
                ''
            ) as cb_first_name_norm,
            split(
                regexp_replace(
                    regexp_replace(normalize(upper(cb_last_name), nfd), r'\pM', ''),
                    '-',
                    ' '
                ),
                ' '
            ) as cb_last_name_tok,
        from gaps
    ),

    tier_s as (
        select
            g.test, g.cb_id, p.student_number, logical_or(g.cb_dob = p.dob) as dob_ok,
        from gaps_norm as g
        inner join ps as p on g.secondary_id = p.student_number
        group by g.test, g.cb_id, p.student_number
    ),

    tier_ab as (
        select g.test, g.cb_id, p.student_number, 'A_B' as tier,
        from gaps_norm as g
        inner join
            ps as p
            on g.cb_dob = p.dob
            and (
                upper(g.cb_last_name) = upper(p.last_name)
                or g.cb_last_name_stripped = p.last_name_stripped
            )
    ),

    tier_c_raw as (
        select g.test, g.cb_id, p.student_number, t1, t2,
        from gaps_norm as g
        inner join ps as p on g.cb_dob = p.dob
        cross join unnest(p.last_name_tok) as t1
        cross join unnest(g.cb_last_name_tok) as t2
    ),

    tier_c as (
        select distinct test, cb_id, student_number, 'C' as tier,
        from tier_c_raw
        where t1 = t2
    ),

    tier_d as (
        select g.test, g.cb_id, p.student_number, 'D' as tier,
        from gaps_norm as g
        inner join
            ps as p
            on abs(date_diff(p.dob, g.cb_dob, day)) in (365, 366)
            and g.cb_last_name_stripped = p.last_name_stripped
            and g.cb_first_name_norm = p.first_name_norm
    ),

    all_tiers as (
        select test, cb_id, student_number, tier,
        from tier_ab

        union all

        select test, cb_id, student_number, tier,
        from tier_c

        union all

        select test, cb_id, student_number, tier,
        from tier_d
    ),

    combined as (
        select
            test,
            cb_id,
            student_number,

            string_agg(distinct tier order by tier) as tiers,
        from all_tiers
        group by test, cb_id, student_number
    ),

    tiebreak as (
        select c.test, c.cb_id, c.student_number, c.tiers,
        from combined as c
        inner join gaps_norm as g on c.test = g.test and c.cb_id = g.cb_id
        inner join ps as p on c.student_number = p.student_number
        where g.cb_first_name_norm = p.first_name_norm
    ),

    per_gap as (
        select
            g.test,
            g.cb_id,

            count(distinct c.student_number) as n_combined,
            count(distinct t.student_number) as n_tiebreak,
            any_value(c.student_number) as combined_student_number,
            any_value(c.tiers) as combined_tiers,
            any_value(t.student_number) as tiebreak_student_number,
            any_value(t.tiers) as tiebreak_tiers,
        from gaps_norm as g
        left join combined as c on g.test = c.test and g.cb_id = c.cb_id
        left join tiebreak as t on g.test = t.test and g.cb_id = t.cb_id
        group by g.test, g.cb_id
    ),

    name_resolved as (
        select
            test,
            cb_id,

            if(
                n_combined = 1, combined_student_number, tiebreak_student_number
            ) as student_number,
            if(n_combined = 1, combined_tiers, tiebreak_tiers) as tiers,
        from per_gap
        where n_combined = 1 or (n_combined > 1 and n_tiebreak = 1)
    ),

    name_gender as (
        select
            nr.test,
            nr.cb_id,
            nr.student_number,
            nr.tiers,

            logical_or(g.cb_gender = p.gender) as gender_ok,
        from name_resolved as nr
        left join tier_s as s on nr.test = s.test and nr.cb_id = s.cb_id
        inner join gaps_norm as g on nr.test = g.test and nr.cb_id = g.cb_id
        inner join ps as p on nr.student_number = p.student_number
        where s.cb_id is null
        group by nr.test, nr.cb_id, nr.student_number, nr.tiers
    ),

    candidates as (
        select
            test,
            cb_id,
            student_number,

            'S' as tiers,
            if(dob_ok, 'resolved', 'flagged_for_review') as bucket,
        from tier_s

        union all

        select
            test,
            cb_id,
            student_number,
            tiers,

            if(tiers = 'A_B' or gender_ok, 'resolved', 'flagged_for_review') as bucket,
        from name_gender
    )

select test, cb_id, student_number, tiers, bucket,
from candidates

union all

select
    g.test,
    g.cb_id,

    cast(null as int64) as student_number,
    cast(null as string) as tiers,
    'no_match' as bucket,
from gaps_norm as g
left join candidates as c on g.test = c.test and g.cb_id = c.cb_id
where c.cb_id is null
order by bucket, test, cb_id
