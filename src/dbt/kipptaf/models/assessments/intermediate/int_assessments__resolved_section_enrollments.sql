with
    -- internal scores: one row per (student, canonical assessment, source).
    -- anchor = the scheduled administration date (administered_date). date_taken
    -- is NOT used -- it is occasionally corrupt (epoch / year-2000 sentinels) and
    -- the wrong grain; anchoring on it dropped scores whose bad date missed every
    -- enrollment window (#4183). The academic year is
    -- not carried: the half-open enrollment window [cc_dateenrolled, cc_dateleft)
    -- pins the section to the year the assessment was actually sat. Adding a
    -- year-equality predicate is redundant for state scores and wrong for
    -- internal -- scaffold.academic_year (academic_year_clean) and the
    -- inventory's illuminate_academic_year (cc_academic_year + 1) use offset
    -- conventions that disagree by a school year.
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    internal_anchored as (
        select
            sc.powerschool_student_number,
            sc.canonical_assessment_id,
            sc.subject_area,
            sc._dbt_source_project,

            c.administered_date as anchor_date,
        from {{ ref("int_assessments__scaffold") }} as sc
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on sc.canonical_assessment_id = c.canonical_assessment_id
        where sc.is_internal_assessment and not sc.is_replacement
    ),

    internal_deduplicated as (
        {{
            dbt_utils.deduplicate(
                relation="internal_anchored",
                partition_by="""
                    powerschool_student_number,
                    canonical_assessment_id,
                    _dbt_source_project
                """,
                order_by="anchor_date asc",
            )
        }}
    ),

    internal_scores as (
        select
            powerschool_student_number,
            canonical_assessment_id,
            subject_area,
            _dbt_source_project,
            anchor_date,

            cast(null as int64) as academic_year,
            cast(null as string) as administration_period,

            'internal' as source_type,
        from internal_deduplicated
    ),

    -- NJ state scores (Pearson). illuminate_subject is the upstream state->course
    -- subject mapping (English Language Arts% -> Text Study, Algebra/Geometry ->
    -- Mathematics, else passthrough), aligning with inventory illuminate_subject_area.
    -- rows with no test date or no student cannot resolve -> dropped (out of scope).
    state_nj_scores as (
        select
            localstudentidentifier as powerschool_student_number,
            academic_year,
            administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            test_date as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'state_nj' as source_type,
        from {{ ref("int_pearson__all_assessments") }}
        where test_date is not null and localstudentidentifier is not null
    ),

    -- FL state scores (FLDOE). administration_window is the FL analogue of
    -- administration_period.
    state_fl_scores as (
        select
            student_number as powerschool_student_number,
            academic_year,
            administration_window as administration_period,
            illuminate_subject as subject_area,
            _dbt_source_project,

            test_date as anchor_date,

            cast(null as int64) as canonical_assessment_id,

            'state_fl' as source_type,
        from {{ ref("int_fldoe__all_assessments") }}
        where test_date is not null and student_number is not null
    ),

    scores as (
        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from internal_scores

        union all

        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from state_nj_scores

        union all

        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            anchor_date,
            source_type,
        from state_fl_scores
    ),

    -- course_subject is the section subject the resolver matches against. For
    -- internal scores subject_area already equals the inventory's
    -- illuminate_subject_area; for state scores the state->course mapping is
    -- already applied upstream (illuminate_subject), so this is a passthrough.
    -- Derived as a named column (not inline in a join) per src/dbt/CLAUDE.md.
    -- score_grain_key is the stable per-score handle used for the tier-2
    -- anti-join (internal grain: canonical; state grain: year/period/subject).
    scores_mapped as (
        select
            *,

            subject_area as course_subject,

            {{
                dbt_utils.generate_surrogate_key(
                    [
                        "powerschool_student_number",
                        "_dbt_source_project",
                        "canonical_assessment_id",
                        "academic_year",
                        "administration_period",
                        "subject_area",
                    ]
                )
            }} as score_grain_key,
        from scores
    ),

    -- tier 1: subject-matching section active on the anchor date (half-open window)
    candidates_subject as (
        select
            s.powerschool_student_number,
            s.canonical_assessment_id,
            s.academic_year,
            s.administration_period,
            s.subject_area,
            s._dbt_source_project,
            s.source_type,
            s.score_grain_key,

            ce.cc_dcid,
            ce._dbt_source_project as cc_source_project,
            ce.cc_dateleft,

            1 as tier,

            'subject_section' as resolution_type,
        from scores_mapped as s
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on s.powerschool_student_number = ce.powerschool_student_number
            and s._dbt_source_project = ce._dbt_source_project
            and s.course_subject = ce.illuminate_subject_area
            and s.anchor_date >= ce.cc_dateenrolled
            and s.anchor_date < ce.cc_dateleft
            -- only sections with a real course-enrollment row resolve to a
            -- dim_student_section_enrollments FK; synthetic ES-Writing (RHET)
            -- inventory rows carry cc_dcid = null and have no dim row
            and ce.cc_dcid is not null
    ),

    -- grain projection: every selected column is functionally determined
    -- by the partition key; not a mask for upstream duplicates
    resolved_subject_keys as (select distinct score_grain_key, from candidates_subject),

    -- scores that found no subject section, eligible for the homeroom tier
    scores_unresolved as (
        select s.*,
        from scores_mapped as s
        left join resolved_subject_keys as cs on s.score_grain_key = cs.score_grain_key
        where cs.score_grain_key is null
    ),

    -- tier 2: the student's homeroom section active on the anchor date
    candidates_homeroom as (
        select
            s.powerschool_student_number,
            s.canonical_assessment_id,
            s.academic_year,
            s.administration_period,
            s.subject_area,
            s._dbt_source_project,
            s.source_type,
            s.score_grain_key,

            ce.cc_dcid,
            ce._dbt_source_project as cc_source_project,
            ce.cc_dateleft,

            2 as tier,

            'homeroom' as resolution_type,
        from scores_unresolved as s
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on s.powerschool_student_number = ce.powerschool_student_number
            and s._dbt_source_project = ce._dbt_source_project
            and ce.courses_credittype = 'HR'
            and s.anchor_date >= ce.cc_dateenrolled
            and s.anchor_date < ce.cc_dateleft
            and ce.cc_dcid is not null
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    all_candidates as (
        select *,
        from candidates_subject

        union all

        select *,
        from candidates_homeroom
    ),

    -- one section per score: prefer the subject section (tier 1) over homeroom,
    -- then the section that ends latest among ties within a tier
    resolved as (
        {{
            dbt_utils.deduplicate(
                relation="all_candidates",
                partition_by="score_grain_key",
                order_by="tier asc, cc_dateleft desc, cc_dcid desc",
            )
        }}
    )

select
    powerschool_student_number,
    canonical_assessment_id,
    academic_year,
    administration_period,
    subject_area,
    _dbt_source_project,
    cc_source_project,
    source_type,
    resolution_type,

    {{ dbt_utils.generate_surrogate_key(["cc_dcid", "cc_source_project"]) }}
    as student_section_enrollment_key,
from resolved
