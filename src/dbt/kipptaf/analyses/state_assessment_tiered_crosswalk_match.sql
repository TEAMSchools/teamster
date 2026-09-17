-- State assessment crosswalk: tiered match for unresolved localstudentidentifier
--
-- Produces candidate Student_Test_UUID -> Student_Number pairs for the
-- crosswalk sheet, for every assessment row the detector
-- (test_incorrect_student_number_pearson) flags. Self-scoping: each gap
-- matches within its OWN academic_year and district, so no year parameter.
--
-- The three matching criteria, in the order they bind:
--
-- 1. ENROLLMENT GATE (hard, every tier). The candidate must have an
-- enrollment row for the test's own academic_year AND district with
-- rn_year = 1. The crosswalk only overrides localstudentidentifier; the
-- downstream join still needs year and district to land. A candidate that
-- fails this gate is unmatchable from the sheet -- a row entered for it
-- changes nothing and never expires -- so it is reported as no_match with
-- reason 'no_enrollment_that_year', never as resolved.
--
-- 2. GRADE COROBORATION. Test codes ELA03-ELA08 / MAT03-MAT08 / SCI05 / SCI08
-- / SOC08 encode the grade in their last two digits, so enrollment
-- grade_level must equal it -- HARD GATE, a mismatch routes to
-- flagged_for_review. HS codes (ALG01, ALG02, GEO01, ELA09, ELA10, ELAGP,
-- MATGP, SCI11) do NOT encode grade: students sit Algebra I in grade 8 or
-- 9, and the graduation-pathway tests in 11. For those the check is
-- INFORMATIONAL only and never gates.
--
-- 3. IDENTITY. state_student_identifier, first name, last name, and date of
-- birth, combined into the tiers below.
--
-- Tiers:
-- A - state id + first + last + DOB all match. Strongest.
-- B - state id + first + last match, no usable DOB on the row. Weaker than
-- it looks: state ids are known unreliable (#3954), so Tier B rests on
-- a wrong-but-real state id also belonging to a same-named enrolled
-- student. A high bar, not an impossible one for common names. Tier B
-- fires on ANY row whose DOB is missing or unparseable, not only on
-- feeds that structurally lack one -- check gap_dob coverage before
-- assuming which assessments land here.
-- C - DOB + first + last match, state id does NOT. Catches a row whose state
-- id is itself wrong, which the absent/present-but-wrong split does not.
-- D - DOB + last name match, first name differs. Nicknames. Annotated, and
-- never auto-resolved when it is the only tier that fired.
--
-- DOB availability is uneven and this is not a vendor property:
-- stg_pearson__njsla / _njsla_science / _parcc carry birthdate only because
-- they `select * except (...)`, so it rides through unnamed. stg_cambium__njgpa
-- and stg_pearson__njgpa use explicit column lists that omit it. Pearson NJGPA
-- is deprecated so it will not accrue new rows; Cambium runs on Tier B.
--
-- The formats differ too, and silently. PARCC ships M/D/YYYY, NJSLA and NJSLA
-- Science ship YYYY-MM-DD. An earlier version parsed only the ISO form, which
-- nulled all 15,625 PARCC birth dates and demoted every PARCC gap to Tier B
-- with nothing to signal it. Before adding a feed here, check its format
-- rather than assuming.
--
-- Buckets: every flagged row lands in exactly one.
-- resolved          - one candidate, grade check passed or not applicable
-- flagged_for_review - one candidate, but the grade hard gate failed, or the
-- only evidence was Tier D
-- ambiguous         - more than one candidate satisfied a tier. The proposed
-- student number is withheld: picked collapses with
-- any_value, so naming one would be a coin flip.
-- no_match          - no tier was satisfied at all
--
-- No fuzzy matching. Every transform is a deterministic string operation.
with
    gaps as (
        select
            a.studenttestuuid,
            a.assessment_version,
            a.academic_year,
            a.localstudentidentifier,
            a.statestudentidentifier,
            a._dbt_source_project,

            a.aligned_test_code as test_code,

            upper(trim(a.firstname)) as gap_first,
            upper(trim(a.lastorsurname)) as gap_last,
        from {{ ref("int_pearson__all_assessments") }} as a
        left join
            {{ ref("base_powerschool__student_enrollments") }} as e
            on a.localstudentidentifier = e.student_number
            and a.academic_year = e.academic_year
            and a._dbt_source_project = e._dbt_source_project
            and e.rn_year = 1
        where
            a.academic_year >= 2017
            and (e.student_number is null or a.localstudentidentifier is null)
    ),

    -- Only these three feeds carry a birth date; see the header note.
    dob_source as (
        select studenttestuuid, birthdate,
        from {{ ref("stg_pearson__njsla") }}

        union all

        select studenttestuuid, birthdate,
        from {{ ref("stg_pearson__njsla_science") }}

        union all

        select studenttestuuid, birthdate,
        from {{ ref("stg_pearson__parcc") }}
    ),

    gaps_graded as (
        select
            g.studenttestuuid,
            g.assessment_version,
            g.academic_year,
            g.localstudentidentifier,
            g.statestudentidentifier,
            g._dbt_source_project,
            g.test_code,
            g.gap_first,
            g.gap_last,

            d.birthdate as gap_dob_raw,

            regexp_extract(g.test_code, r'(0[3-8])$') as encoded_grade_str,
        from gaps as g
        left join dob_source as d on g.studenttestuuid = d.studenttestuuid
    ),

    gaps_typed as (
        select
            studenttestuuid,
            assessment_version,
            academic_year,
            localstudentidentifier,
            statestudentidentifier,
            _dbt_source_project,
            test_code,
            gap_first,
            gap_last,

            cast(encoded_grade_str as int64) as expected_grade,

            -- PARCC ships M/D/YYYY while NJSLA and NJSLA Science ship
            -- YYYY-MM-DD. Parsing only the ISO form silently nulls every
            -- PARCC birth date and demotes those rows to Tier B.
            coalesce(
                safe.parse_date('%Y-%m-%d', gap_dob_raw),
                safe.parse_date('%m/%d/%Y', gap_dob_raw)
            ) as gap_dob,
        from gaps_graded
    ),

    ps as (
        select
            student_number,
            academic_year,
            _dbt_source_project,
            grade_level,
            dob,
            state_studentnumber,

            upper(trim(first_name)) as ps_first,
            upper(trim(last_name)) as ps_last,
        from {{ ref("base_powerschool__student_enrollments") }}
        where rn_year = 1
    ),

    -- The enrollment gate: every candidate below is already year- and
    -- district-scoped by this join, so no tier can resolve a student who was
    -- not enrolled when the test was taken.
    candidates as (
        select
            g.studenttestuuid,
            g.assessment_version,
            g.academic_year,
            g.test_code,
            g.expected_grade,
            g.gap_first,
            g.gap_last,
            g.gap_dob,
            g.statestudentidentifier,

            p.student_number,
            p.grade_level,
            p.dob,
            p.ps_first,
            p.ps_last,

            cast(g.statestudentidentifier as string)
            = cast(p.state_studentnumber as string) as state_id_match,
            g.gap_first = p.ps_first as first_match,
            g.gap_last = p.ps_last as last_match,
            g.gap_dob = p.dob as dob_match,
        from gaps_typed as g
        inner join
            ps as p
            on g.academic_year = p.academic_year
            and g._dbt_source_project = p._dbt_source_project
    ),

    tiered as (
        select
            studenttestuuid,
            student_number,
            expected_grade,
            grade_level,
            gap_dob,
            test_code,
            assessment_version,

            case
                when state_id_match and first_match and last_match and dob_match
                then 'A'
                when state_id_match and first_match and last_match and gap_dob is null
                then 'B'
                when dob_match and first_match and last_match and not state_id_match
                then 'C'
                when dob_match and last_match and not first_match
                then 'D'
            end as tier,
        from candidates
    ),

    matched as (
        select
            studenttestuuid,
            student_number,
            tier,
            expected_grade,
            grade_level,
            test_code,
            assessment_version,
        from tiered
        where tier is not null
    ),

    per_gap as (
        select studenttestuuid, count(distinct student_number) as n_candidates,
        from matched
        group by studenttestuuid
    ),

    -- Valid only where n_candidates = 1, enforced in the final WHERE.
    picked as (
        select
            studenttestuuid,
            any_value(student_number) as student_number,
            any_value(expected_grade) as expected_grade,
            any_value(grade_level) as grade_level,
            any_value(test_code) as test_code,
            any_value(assessment_version) as assessment_version,
            string_agg(distinct tier order by tier) as tiers,
        from matched
        group by studenttestuuid
    ),

    scored as (
        select
            p.studenttestuuid,
            p.student_number,
            p.tiers,
            p.test_code,
            p.assessment_version,
            p.expected_grade,
            p.grade_level,

            pg.n_candidates,

            p.expected_grade is null as grade_is_informational,
            p.expected_grade = p.grade_level as grade_matches,
        from picked as p
        inner join per_gap as pg on p.studenttestuuid = pg.studenttestuuid
    )

select
    s.studenttestuuid as student_test_uuid,
    s.tiers,
    s.assessment_version,
    s.test_code,
    s.expected_grade,
    s.grade_level,
    s.grade_is_informational,

    -- picked collapses with any_value, so for an ambiguous gap the candidate
    -- is an arbitrary one of several. Withhold it rather than present a
    -- coin-flip as a proposal.
    if(
        s.n_candidates > 1, cast(null as int64), s.student_number
    ) as proposed_student_number,

    case
        when s.n_candidates > 1
        then 'ambiguous'
        when not s.grade_is_informational and not s.grade_matches
        then 'flagged_for_review'
        when s.tiers = 'D'
        then 'flagged_for_review'
        else 'resolved'
    end as bucket,
from scored as s

union all

select
    g.studenttestuuid as student_test_uuid,
    cast(null as string) as tiers,
    g.assessment_version,
    g.test_code,
    g.expected_grade,
    cast(null as int64) as grade_level,
    cast(null as bool) as grade_is_informational,
    cast(null as int64) as proposed_student_number,

    'no_match' as bucket,
from gaps_typed as g
left join picked as pk on g.studenttestuuid = pk.studenttestuuid
where pk.studenttestuuid is null
order by bucket, assessment_version, student_test_uuid
