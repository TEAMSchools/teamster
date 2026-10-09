with
    -- Per `src/dbt/CLAUDE.md` hash-derivation rule: fact must re-join
    -- int_assessments__assessments_members to read raw `academic_year`, since
    -- response_rollup propagates `academic_year_clean as academic_year`
    -- (+1 offset) while dim_assessment_administrations hashes the raw value.
    internal_assessments as (
        select
            rr.powerschool_student_number as student_number,
            rr.assessment_id,
            rr.response_type_id,
            rr.response_type_code,
            rr.response_type_description,
            rr.response_type_root_description,
            rr.is_replacement,
            rr.performance_band_label,
            rr.performance_band_label_number,
            rr.is_mastery,
            rr.n_assessments,
            rr.percent_correct,
            rr._dbt_source_project,

            rr.date_taken as test_date,

            -- Null here is a real assigned-but-not-taken record, not a join
            -- defect: response_rollup LEFT JOINs responses onto the scaffold's
            -- "expected to take" grain.
            coalesce(rr.response_type, 'not_taken') as response_type,

            to_json_string(rr.assessment_ids) as assessment_ids_json,

            rr.assessment_id as source_assessment_id,

            a.academic_year,
            a.module_code,

            c.administered_date,

            coalesce(c.administered_date, rr.date_taken) as assessment_date_key,

            cast(null as numeric) as scale_score,

            rr.performance_band_label as proficiency_level,

            'internal' as score_source,
        from {{ ref("int_assessments__response_rollup") }} as rr
        inner join
            {{ ref("int_assessments__assessments_members") }} as a
            on rr.assessment_id = a.assessment_id
        inner join
            {{ ref("int_assessments__assessments_canonical") }} as c
            on a.canonical_assessment_id = c.canonical_assessment_id
        where rr.is_internal_assessment
    ),

    state_union as (
        select
            student_number,
            academic_year,
            subject_area,
            module_code,
            administration_period,
            assessment_type,
            scale_score,
            is_proficient,
            test_date,
            score_source,
            _dbt_source_project,

            performance_level_label as performance_band,
            illuminate_subject_area as illuminate_subject,

            cast(null as numeric) as percent_correct,
        from {{ ref("int_assessments__state_scores") }}
        where
            scale_score is not null
            and (
                score_source = 'state_fl'
                or academic_year >= {{ var("current_academic_year") - 7 }}
            )
    ),

    -- iReady overall and DIBELS benchmark rows (Composite as overall, each
    -- sub-measure as group). DIBELS is already unique at the (student, year,
    -- period, date, measure_standard) grain, so no dedupe here. The unique test
    -- on assessment_score_key is what holds that.
    benchmark_scores as (
        select
            student_number,
            academic_year,
            module_code,
            raw_subject,
            source_system,
            administration_period,
            test_date,
            _dbt_source_project,
            proficiency_level,
            score_source,
            scale_score,
            national_percentile,
            is_mastery,
            response_type,
            response_type_code,
            response_type_description,

            illuminate_subject_area as illuminate_subject,
        from {{ ref("int_assessments__benchmark_scores") }}
        where
            (
                score_source = 'iready'
                and rn_subj_day = 1
                and _dbt_source_project is not null
                and test_date is not null
                and scale_score is not null
            )
            or (score_source = 'dibels' and test_date is not null)
    ),

    -- Domain-level rows. module_code stays the subject so these rows hash to
    -- the same assessment_administration_key as the subject's overall row.
    -- No 'relative_placement is not null' predicate
    -- because int_assessments__iready_domain_unpivot already enforces it (#4709).
    iready_domain_scores_raw as (
        select
            student_id as student_number,
            academic_year_int as academic_year,
            `subject` as module_code,
            `subject` as raw_subject,
            test_round as administration_period,
            completion_date as test_date,
            _dbt_source_project,

            relative_placement as proficiency_level,

            'iready' as source_system,
            'iready' as score_source,
            'group' as response_type,

            domain_name as response_type_code,

            initcap(replace(domain_name, '_', ' ')) as response_type_description,

            cast(scale_score as numeric) as scale_score,
            cast(null as numeric) as national_percentile,

            -- Matched on labels, not an ordinal, because no per-domain
            -- equivalent of overall_relative_placement_int exists upstream. The
            -- accepted_values test on relative_placement guards the strings.
            relative_placement
            in ('Early On Grade Level', 'Mid or Above Grade Level') as is_mastery,
        from {{ ref("int_assessments__iready_domain_unpivot") }}
        where
            completion_date is not null
            and _dbt_source_project is not null
            and relative_placement != 'Not Assessed'
            and domain_name != 'comprehension_overall'
            and rn_subj_day = 1
    ),

    iready_domain_scores as (
        select
            d.student_number,
            d.academic_year,
            d.module_code,
            d.raw_subject,
            d.source_system,
            d.administration_period,
            d.test_date,
            d._dbt_source_project,
            d.proficiency_level,
            d.score_source,
            d.scale_score,
            d.national_percentile,
            d.is_mastery,
            d.response_type,
            d.response_type_code,
            d.response_type_description,

            coalesce(x.illuminate_subject_area, d.raw_subject) as illuminate_subject,
        from iready_domain_scores_raw as d
        left join
            {{ ref("stg_google_sheets__assessments__vendor_subject_crosswalk") }} as x
            on d.source_system = x.source_system
            and d.raw_subject = x.raw_subject
    ),

    star_scores_raw as (
        select
            student_number,
            academic_year,
            module_code,
            raw_subject,
            source_system,
            administration_period,
            test_date,
            _dbt_source_project,
            proficiency_level,
            score_source,
            scale_score,
            national_percentile,
            is_mastery,
            response_type,
            response_type_code,
            response_type_description,
            assessment_id,

            illuminate_subject_area as illuminate_subject,
        from {{ ref("int_assessments__benchmark_scores") }}
        where
            score_source = 'star'
            and test_date is not null
            and scale_score is not null
            and _dbt_source_project is not null
    ),

    -- This dedupe is permanent, not a workaround for #4388. STAR records each
    -- sitting under its own assessment_id, and students genuinely retest the
    -- same subject on the same day -- 144 rows as of 2026-09-01 -- so the fact
    -- grain (which carries no attempt dimension) is coarser than staging on
    -- purpose. scale_score desc keeps the best sitting.
    -- partition_by deliberately omits academic_year: a physical test pulled
    -- under two fiscal-year partitions has the same test_date but a differing
    -- pull-derived academic_year, so keying on academic_year would keep both
    -- rows -- they then double-count once academic_year is resolved from the
    -- test date (#4546). A date belongs to exactly one academic year, so
    -- collapsing on test_date (sans academic_year) only ever merges re-pulls,
    -- never distinct sittings. academic_year desc makes the survivor
    -- deterministic.
    -- Measured at 8,128 input rows for #5252 -- below the ~1M threshold for the
    -- ranked-column rewrite, so this stays on the macro. Don't re-measure.
    star_scores as (
        {{
            dbt_utils.deduplicate(
                relation="star_scores_raw",
                partition_by="""
                    _dbt_source_project,
                    student_number,
                    administration_period,
                    module_code,
                    test_date
                """,
                order_by="scale_score desc, assessment_id desc, academic_year desc",
            )
        }}
    ),

    vendor_all as (
        select
            student_number,
            academic_year,
            module_code,
            raw_subject,
            source_system,
            administration_period,
            test_date,
            _dbt_source_project,
            proficiency_level,
            score_source,
            scale_score,
            national_percentile,
            is_mastery,
            response_type,
            response_type_code,
            response_type_description,
            illuminate_subject,
        from benchmark_scores

        union all

        select
            student_number,
            academic_year,
            module_code,
            raw_subject,
            source_system,
            administration_period,
            test_date,
            _dbt_source_project,
            proficiency_level,
            score_source,
            scale_score,
            national_percentile,
            is_mastery,
            response_type,
            response_type_code,
            response_type_description,
            illuminate_subject,
        from star_scores

        union all

        select
            student_number,
            academic_year,
            module_code,
            raw_subject,
            source_system,
            administration_period,
            test_date,
            _dbt_source_project,
            proficiency_level,
            score_source,
            scale_score,
            national_percentile,
            is_mastery,
            response_type,
            response_type_code,
            response_type_description,
            illuminate_subject,
        from iready_domain_scores
    ),

    -- Reporting quarters. A score's quarter comes from the date it was
    -- administered or taken, NOT from its section enrollment: a section spans
    -- several quarters, so "the quarter for a section enrollment" is not well
    -- defined (#4484). Resolved per score row rather than in
    -- int_assessments__resolved_section_enrollments, which is one row per score
    -- GRAIN — scores sharing a grain can carry different dates. RT rows abut but
    -- never overlap within a (school_id, region), so BETWEEN matches one row.
    reporting_terms as (
        select
            `type`, code, `name`, `start_date`, end_date, region, school_id, grade_band,
        from {{ ref("stg_google_sheets__reporting__terms") }}
        where `type` = 'RT'
    )

/* internal assessments */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "ia.student_number",
                "ia.assessment_id",
                "ia.assessment_ids_json",
                "ia.response_type",
                "ia.response_type_id",
                "ia.response_type_code",
            ]
        )
    }} as assessment_score_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "'illuminate'",
                "ia.module_code",
                "ia.administered_date",
                "ia.academic_year",
                "ia._dbt_source_project",
                "null",
                "ia.source_assessment_id",
                "null",
            ]
        )
    }} as assessment_administration_key,

    if(
        rt.code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt.type",
                    "rt.code",
                    "rt.name",
                    "rt.start_date",
                    "rt.region",
                    "rt.school_id",
                    "rt.grade_band",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,

    sr.student_section_enrollment_key,

    ia.test_date as test_date_key,
    ia.assessment_date_key,

    ia.scale_score,
    ia.percent_correct,

    cast(null as numeric) as national_percentile,

    ia.proficiency_level,
    ia.is_mastery,
    ia.response_type,
    ia.response_type_code,
    ia.response_type_description,
    ia.response_type_root_description,
    ia.is_replacement,
    ia.performance_band_label_number,

    sr.resolution_type as enrollment_resolution,
from internal_assessments as ia
-- ia.assessment_id is canonical-grain: int_assessments__response_rollup aliases
-- canonical_assessment_id as assessment_id, so it matches the resolver's
-- canonical_assessment_id join key. INNER drops internal scores with no
-- resolved section (out of scope) -- the resolver is the scope of record.
inner join
    {{ ref("int_assessments__resolved_section_enrollments") }} as sr
    on ia.student_number = sr.powerschool_student_number
    and ia.assessment_id = sr.canonical_assessment_id
    and ia._dbt_source_project = sr._dbt_source_project
    and sr.source_type = 'internal'
left join
    reporting_terms as rt
    on sr.powerschool_school_id = rt.school_id
    and sr.region = rt.region
    and ia.assessment_date_key between rt.`start_date` and rt.end_date

union all

/* state assessments */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "su._dbt_source_project",
                "su.student_number",
                "su.academic_year",
                "su.administration_period",
                "su.subject_area",
            ]
        )
    }} as assessment_score_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "su.assessment_type",
                "su.module_code",
                "null",
                "su.academic_year",
                "su._dbt_source_project",
                "su.administration_period",
                "null",
                "null",
            ]
        )
    }} as assessment_administration_key,

    if(
        rt.code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt.type",
                    "rt.code",
                    "rt.name",
                    "rt.start_date",
                    "rt.region",
                    "rt.school_id",
                    "rt.grade_band",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,

    sr.student_section_enrollment_key,

    su.test_date as test_date_key,
    su.test_date as assessment_date_key,

    su.scale_score,
    su.percent_correct,

    cast(null as numeric) as national_percentile,

    su.performance_band as proficiency_level,
    su.is_proficient as is_mastery,

    'overall' as response_type,
    cast(null as string) as response_type_code,
    cast(null as string) as response_type_description,
    cast(null as string) as response_type_root_description,
    cast(null as bool) as is_replacement,
    cast(null as numeric) as performance_band_label_number,

    sr.resolution_type as enrollment_resolution,
from state_union as su
-- the resolver keys state scores on illuminate_subject (the crosswalk's
-- state->Illuminate subject mapping), not the raw subject_area the
-- assessment_score_key hashes. join on su.illuminate_subject = sr.subject_area
-- or every row drops. INNER scopes the fact to state scores with a resolved
-- section.
inner join
    {{ ref("int_assessments__resolved_section_enrollments") }} as sr
    on su.student_number = sr.powerschool_student_number
    and su.academic_year = sr.academic_year
    and su.administration_period = sr.administration_period
    and su.illuminate_subject = sr.subject_area
    and su._dbt_source_project = sr._dbt_source_project
    and sr.source_type in ('state_nj', 'state_fl')
left join
    reporting_terms as rt
    on sr.powerschool_school_id = rt.school_id
    and sr.region = rt.region
    and su.test_date between rt.`start_date` and rt.end_date

union all

/* vendor assessments (iReady, STAR, DIBELS) */
select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "va.score_source",
                "va._dbt_source_project",
                "va.student_number",
                "va.academic_year",
                "va.administration_period",
                "va.module_code",
                "va.test_date",
                "va.response_type_code",
            ]
        )
    }} as assessment_score_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "va.score_source",
                "va.module_code",
                "null",
                "va.academic_year",
                "va._dbt_source_project",
                "va.administration_period",
                "null",
                "null",
            ]
        )
    }} as assessment_administration_key,

    if(
        rt.code is not null,
        {{
            dbt_utils.generate_surrogate_key(
                [
                    "rt.type",
                    "rt.code",
                    "rt.name",
                    "rt.start_date",
                    "rt.region",
                    "rt.school_id",
                    "rt.grade_band",
                ]
            )
        }},
        cast(null as string)
    ) as term_key,

    sr.student_section_enrollment_key,

    va.test_date as test_date_key,
    va.test_date as assessment_date_key,

    va.scale_score,

    cast(null as numeric) as percent_correct,

    va.national_percentile,
    va.proficiency_level,
    va.is_mastery,
    va.response_type,
    va.response_type_code,
    va.response_type_description,

    cast(null as string) as response_type_root_description,
    cast(null as bool) as is_replacement,
    cast(null as numeric) as performance_band_label_number,

    sr.resolution_type as enrollment_resolution,
from vendor_all as va
-- the resolver keys vendor scores on illuminate_subject (the crosswalk's
-- vendor->Illuminate subject mapping), not the raw vendor subject the
-- assessment_score_key hashes. INNER scopes the fact to vendor scores with a
-- resolved section.
inner join
    {{ ref("int_assessments__resolved_section_enrollments") }} as sr
    on va.student_number = sr.powerschool_student_number
    and va.academic_year = sr.academic_year
    and va.administration_period = sr.administration_period
    and va.illuminate_subject = sr.subject_area
    and va._dbt_source_project = sr._dbt_source_project
    and va.score_source = sr.source_type
left join
    reporting_terms as rt
    on sr.powerschool_school_id = rt.school_id
    and sr.region = rt.region
    and va.test_date between rt.`start_date` and rt.end_date
