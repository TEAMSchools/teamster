with
    -- Union of regions_assessed across all members of a canonical group.
    -- Canonical members may individually be tagged for different regions
    -- (e.g., one tagged Miami, another tagged Camden/Newark/Paterson). The
    -- canonical-keyed dim must emit one row per (canonical, any-member-region).
    canonical_regions as (
        select
            canonical_assessment_id,
            array_agg(distinct region) as canonical_regions_array,
        from
            {{ ref("int_assessments__assessments") }},
            unnest(regions_assessed_array) as region
        where is_internal_assessment
        group by canonical_assessment_id
    ),

    illuminate_administrations as (
        select distinct
            'illuminate' as assessment_type,

            a.canonical_title as title,

            a.subject_area,
            a.scope,
            a.module_code,

            a.canonical_grade_level_id - 1 as grade_level,

            cast(a.canonical_administered_at as date) as administered_date,
            a.academic_year,

            region,

            a.canonical_assessment_id as source_assessment_id,

            cast(null as string) as administration_period,
            cast(null as string) as test_type,
        from {{ ref("int_assessments__assessments") }} as a
        inner join
            canonical_regions as cr
            on a.canonical_assessment_id = cr.canonical_assessment_id
        cross join unnest(cr.canonical_regions_array) as region
        where a.is_internal_assessment
    ),

    -- State NJ: one administration per (testcode, period, academic_year,
    -- region). period acts as the season/window.
    state_nj_administrations as (
        select distinct
            'state' as assessment_type,
            assessment_name as title,

            if(
                `subject` = 'English Language Arts/Literacy',
                'English Language Arts',
                `subject`
            ) as subject_area,

            discipline as scope,

            case
                testcode
                when 'SC05'
                then 'SCI05'
                when 'SC08'
                then 'SCI08'
                when 'SC11'
                then 'SCI11'
                else testcode
            end as module_code,

            test_grade as grade_level,

            cast(null as date) as administered_date,
            academic_year,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

            cast(null as int64) as source_assessment_id,

            if(`period` = 'FallBlock', 'Fall', `period`) as administration_period,

            cast(null as string) as test_type,
        from {{ ref("int_pearson__all_assessments") }}
        where testscalescore is not null
    ),

    -- State FL: one administration per (test_code, administration_window,
    -- academic_year, region).
    state_fl_administrations as (
        select distinct
            'state' as assessment_type,
            assessment_name as title,
            assessment_subject as subject_area,
            discipline as scope,
            test_code as module_code,

            cast(assessment_grade as int) as grade_level,

            cast(null as date) as administered_date,
            academic_year,

            initcap(regexp_extract(_dbt_source_relation, r'kipp(\w+)_')) as region,

            cast(null as int64) as source_assessment_id,

            administration_window as administration_period,

            cast(null as string) as test_type,
        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null
    ),

    -- College Official: one administration per (score_type, test_date,
    -- administration_round). region is null because college tests are
    -- region-agnostic.
    college_administrations as (
        select distinct
            'college' as assessment_type,
            scope as title,
            subject_area,
            scope,
            score_type as module_code,

            cast(null as int64) as grade_level,

            test_date as administered_date,
            academic_year,

            cast(null as string) as region,

            cast(null as int64) as source_assessment_id,

            administration_round as administration_period,

            'Official' as test_type,
        from {{ ref("int_assessments__college_assessment") }}
    ),

    -- College Practice: one administration per (scope, test_date,
    -- administration_round). region is null because college tests are
    -- region-agnostic. Aggregates across subject_area rows in the upstream
    -- model.
    practice_administrations as (
        select
            'college' as assessment_type,
            scope as title,
            any_value(subject_area) as subject_area,
            scope,
            scope as module_code,

            cast(null as int64) as grade_level,

            test_date as administered_date,
            academic_year,

            cast(null as string) as region,
            cast(null as int64) as source_assessment_id,

            administration_round as administration_period,

            'Practice' as test_type,
        from {{ ref("int_assessments__college_assessment_practice") }}
        group by scope, test_date, academic_year, administration_round
    ),

    -- AP: one administration per (subject, academic_year). Test date is
    -- not captured upstream.
    ap_administrations as (
        select distinct
            'ap' as assessment_type,
            concat('AP ', test_subject) as title,
            test_subject as subject_area,

            'AP' as scope,

            ps_ap_course_subject_code as module_code,

            cast(null as int64) as grade_level,

            cast(null as date) as administered_date,
            academic_year,

            cast(null as string) as region,

            cast(null as int64) as source_assessment_id,

            cast(null as string) as administration_period,

            cast(null as string) as test_type,
        from {{ ref("int_assessments__ap_assessments") }}
    ),

    all_administrations as (
        select *,
        from illuminate_administrations
        union all
        select *,
        from state_nj_administrations
        union all
        select *,
        from state_fl_administrations
        union all
        select *,
        from college_administrations
        union all
        select *,
        from practice_administrations
        union all
        select *,
        from ap_administrations
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "assessment_type",
                "module_code",
                "administered_date",
                "academic_year",
                "region",
                "administration_period",
                "source_assessment_id",
                "test_type",
            ]
        )
    }} as assessment_administration_key,

    administered_date as administered_date_key,

    region,
    administration_period,
    source_assessment_id,
    test_type,
from all_administrations
