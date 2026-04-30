with
    -- trunk-ignore(sqlfluff/ST03): referenced by string in dbt_utils.deduplicate
    illuminate_unnested as (
        select
            a.title,
            a.subject_area,
            a.scope,
            a.module_code,
            a.grade_level,

            cast(a.administered_at as date) as administered_date,
            a.academic_year,
            region,
        from {{ ref("int_assessments__assessments") }} as a
        cross join unnest(a.regions_assessed_array) as region
        where a.is_internal_assessment
    ),

    -- Multiple `assessment_id` rows can share the same admin grain
    -- (region-specific copies of the same module checkpoint), so dedupe
    -- here rather than via DISTINCT. Root-cause fix tracked in #3785.
    illuminate_deduped as (
        {{
            dbt_utils.deduplicate(
                relation="illuminate_unnested",
                partition_by=(
                    "title, subject_area, scope, module_code, "
                    "grade_level, administered_date, academic_year, region"
                ),
                order_by="title",
            )
        }}
    ),

    illuminate_administrations as (
        select
            'illuminate' as assessment_type,
            title,
            subject_area,
            scope,
            module_code,
            grade_level,
            administered_date,
            academic_year,
            region,

            cast(null as string) as administration_round,
            cast(null as string) as season,
            cast(null as string) as administration_window,
            cast(null as string) as test_type,
        from illuminate_deduped
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

            cast(null as string) as administration_round,

            if(`period` = 'FallBlock', 'Fall', `period`) as season,
            if(`period` = 'FallBlock', 'Fall', `period`) as administration_window,

            cast(null as string) as test_type,
        from {{ ref("int_pearson__all_assessments") }}
        where testscalescore is not null
    ),

    -- State FL: one administration per (test_code, season, academic_year,
    -- region).
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

            cast(null as string) as administration_round,

            season,
            administration_window,

            cast(null as string) as test_type,
        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null
    ),

    -- College: one administration per (score_type, test_date,
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

            administration_round,

            cast(null as string) as season,
            cast(null as string) as administration_window,

            test_type,
        from {{ ref("int_assessments__college_assessment") }}
    ),

    -- AP: one administration per (subject, academic_year). Test date is
    -- not captured upstream.
    ap_administrations as (
        select distinct
            'college' as assessment_type,
            concat('AP ', test_subject) as title,
            test_subject as subject_area,

            'AP' as scope,

            ps_ap_course_subject_code as module_code,

            cast(null as int64) as grade_level,

            cast(null as date) as administered_date,
            academic_year,

            cast(null as string) as region,
            cast(null as string) as administration_round,
            cast(null as string) as season,
            cast(null as string) as administration_window,

            'Official' as test_type,
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
        from ap_administrations
    )

select
    {{
        dbt_utils.generate_surrogate_key(
            [
                "assessment_type",
                "title",
                "subject_area",
                "scope",
                "module_code",
                "grade_level",
                "administered_date",
                "academic_year",
                "administration_round",
                "region",
                "season",
                "administration_window",
            ]
        )
    }} as assessment_administration_key,

    {{
        dbt_utils.generate_surrogate_key(
            [
                "assessment_type",
                "title",
                "subject_area",
                "scope",
                "module_code",
                "grade_level",
            ]
        )
    }} as assessment_key,

    administered_date as administered_date_key,

    academic_year,
    region,
    administration_round,
    season,
    administration_window,
    test_type,
from all_administrations
