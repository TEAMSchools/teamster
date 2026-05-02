with
    assessment_region_scaffold as (
        select
            a.assessment_id,
            a.title,
            a.academic_year,
            a.academic_year_clean,
            a.administered_at,
            a.subject_area,
            a.performance_band_set_id,
            a.scope,
            a.module_type,
            a.module_code,
            a.canonical_assessment_id,
            a.canonical_title,
            a.canonical_administered_at,
            a.canonical_grade_level_id,

            region,

            coalesce(a.illuminate_grade_level_id, agl.grade_level_id) as grade_level_id,
        from {{ ref("int_assessments__assessments") }} as a
        cross join unnest(a.regions_assessed_array) as region
        left join
            {{ ref("stg_illuminate__dna_assessments__assessment_grade_levels") }} as agl
            on a.assessment_id = agl.assessment_id
        where a.is_internal_assessment
    ),

    -- One row per (powerschool_school_id, region). Sources from
    -- stg_google_sheets__people__locations per kipptaf/CLAUDE.md, not
    -- int_people__location_crosswalk (which is at aliased-name grain).
    -- The (is_campus / is_pathways / Whittier) filter mirrors the canonical
    -- mart-scope filter pattern tracked in #3751 / #3754.
    school_to_region as (
        select powerschool_school_id, city as region,
        from {{ ref("stg_google_sheets__people__locations") }}
        where
            not is_campus
            and not is_pathways
            and location_name != 'KIPP Whittier Elementary'
    ),

    -- trunk-ignore(sqlfluff/ST03)
    internal_assessments as (
        /* K-8 */
        select
            a.assessment_id,
            a.title,
            a.administered_at,
            a.performance_band_set_id,
            a.academic_year_clean,
            a.subject_area,
            a.scope,
            a.module_type,
            a.module_code,
            a.region,
            a.grade_level_id,
            a.canonical_assessment_id,
            a.canonical_title,
            a.canonical_administered_at,
            a.canonical_grade_level_id,

            ssa.student_id as illuminate_student_id,

            s.local_student_id as powerschool_student_number,

            ce.powerschool_school_id,
            ce.cc_dateenrolled,
            ce.cc_dateleft,
            ce.discipline,
            ce.cc_dcid,

            ce._dbt_source_relation as cc_source_relation,
        from assessment_region_scaffold as a
        inner join
            {{ ref("int_illuminate__student_session_aff") }} as ssa
            on a.academic_year = ssa.academic_year
            and a.grade_level_id = ssa.grade_level_id
            and ssa.rn_student_session_desc = 1
        inner join
            {{ ref("stg_illuminate__public__students") }} as s
            on ssa.student_id = s.student_id
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on a.subject_area = ce.illuminate_subject_area
            and a.region = ce.region
            and a.administered_at between ce.cc_dateenrolled and ce.cc_dateleft
            and s.local_student_id = ce.powerschool_student_number
            and not ce.is_advanced_math_student
        where a.grade_level_id <= 9

        union all

        /* HS */
        select
            a.assessment_id,
            a.title,
            a.administered_at,
            a.performance_band_set_id,
            a.academic_year_clean,
            a.subject_area,
            a.scope,
            a.module_type,
            a.module_code,
            a.region,

            ce.illuminate_grade_level_id as grade_level_id,

            a.canonical_assessment_id,
            a.canonical_title,
            a.canonical_administered_at,
            a.canonical_grade_level_id,

            s.student_id as illuminate_student_id,

            ce.powerschool_student_number,
            ce.powerschool_school_id,
            ce.cc_dateenrolled,
            ce.cc_dateleft,
            ce.discipline,
            ce.cc_dcid,

            ce._dbt_source_relation as cc_source_relation,
        from assessment_region_scaffold as a
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on a.subject_area = ce.illuminate_subject_area
            and a.region = ce.region
            and a.administered_at between ce.cc_dateenrolled and ce.cc_dateleft
        inner join
            {{ ref("stg_illuminate__public__students") }} as s
            on ce.powerschool_student_number = s.local_student_id
            and ce.illuminate_grade_level_id >= 10
    ),

    deduplicate as (
        /* we need to join to `int_assessments__course_enrollments` according to
        enrollment dates, but some students have multiple enrollments for the same
        course */
        {{
            dbt_utils.deduplicate(
                relation="internal_assessments",
                partition_by="assessment_id, illuminate_student_id",
                order_by="cc_dateleft desc, cc_dateenrolled desc",
            )
        }}
    )

/* internal assessments */
select
    ia.illuminate_student_id,
    ia.powerschool_student_number,
    ia.assessment_id,
    ia.title,
    ia.subject_area,
    ia.academic_year_clean as academic_year,
    ia.administered_at,
    ia.performance_band_set_id,
    ia.powerschool_school_id,
    ia.region,
    ia.grade_level_id,
    ia.scope,
    ia.module_type,
    ia.module_code,
    ia.discipline,
    ia.cc_dcid,
    ia.cc_source_relation,
    ia.canonical_assessment_id,
    ia.canonical_title,
    ia.canonical_administered_at,
    ia.canonical_grade_level_id,

    sa.student_assessment_id,
    sa.date_taken,

    true as is_internal_assessment,
    false as is_replacement,
from deduplicate as ia
left join
    {{ ref("stg_illuminate__dna_assessments__students_assessments") }} as sa
    on ia.illuminate_student_id = sa.student_id
    and ia.assessment_id = sa.assessment_id

union all

/* K-8 replacement curriculum */
select
    sa.student_id as illuminate_student_id,

    s.local_student_id as powerschool_student_number,

    a.assessment_id,
    a.title,
    a.subject_area,
    a.academic_year_clean as academic_year,
    a.administered_at,
    a.performance_band_set_id,

    ssa.site_id as powerschool_school_id,

    str.region,

    null as grade_level_id,

    a.scope,
    a.module_type,
    a.module_code,

    null as discipline,

    cast(null as int64) as cc_dcid,
    cast(null as string) as cc_source_relation,

    a.canonical_assessment_id,
    a.canonical_title,
    a.canonical_administered_at,
    a.canonical_grade_level_id,

    sa.student_assessment_id,
    sa.date_taken,

    true as is_internal_assessment,
    true as is_replacement,
from {{ ref("int_assessments__assessments") }} as a
inner join
    {{ ref("stg_illuminate__dna_assessments__students_assessments") }} as sa
    on a.assessment_id = sa.assessment_id
inner join
    {{ ref("stg_illuminate__public__students") }} as s on sa.student_id = s.student_id
inner join
    {{ ref("int_illuminate__student_session_aff") }} as ssa
    on sa.student_id = ssa.student_id
    and a.academic_year = ssa.academic_year
    and a.illuminate_grade_level_id != ssa.grade_level_id
    and ssa.rn_student_session_desc = 1
left join school_to_region as str on ssa.site_id = str.powerschool_school_id
where
    a.is_internal_assessment
    and a.subject_area in ('Text Study', 'Mathematics', 'Social Studies', 'Science')
    and a.grade_level <= 8

union all

/* all other assessments */
select
    sa.student_id as illuminate_student_id,

    s.local_student_id as powerschool_student_number,

    a.assessment_id,
    a.title,
    a.subject_area,
    a.academic_year_clean as academic_year,
    a.administered_at,
    a.performance_band_set_id,

    ssa.site_id as powerschool_school_id,

    str.region,

    null as grade_level_id,

    a.scope,
    a.module_type,
    a.module_code,

    null as discipline,

    cast(null as int64) as cc_dcid,
    cast(null as string) as cc_source_relation,

    a.canonical_assessment_id,
    a.canonical_title,
    a.canonical_administered_at,
    a.canonical_grade_level_id,

    sa.student_assessment_id,
    sa.date_taken,

    false as is_internal_assessment,
    false as is_replacement,
from {{ ref("int_assessments__assessments") }} as a
inner join
    {{ ref("stg_illuminate__dna_assessments__students_assessments") }} as sa
    on a.assessment_id = sa.assessment_id
inner join
    {{ ref("stg_illuminate__public__students") }} as s on sa.student_id = s.student_id
inner join
    {{ ref("int_illuminate__student_session_aff") }} as ssa
    on a.academic_year = ssa.academic_year
    and sa.student_id = ssa.student_id
    and ssa.rn_student_session_desc = 1
left join school_to_region as str on ssa.site_id = str.powerschool_school_id
where not a.is_internal_assessment
