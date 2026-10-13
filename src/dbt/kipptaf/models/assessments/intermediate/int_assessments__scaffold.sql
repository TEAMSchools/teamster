with
    assessment_region_scaffold as (
        select
            a.source,
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

            region,

            coalesce(a.tagged_grade_level_id, agl.grade_level_id) as grade_level_id,
        from {{ ref("int_assessments__assessments_members") }} as a
        cross join unnest(a.regions_assessed_array) as region
        left join
            {{ ref("stg_illuminate__dna_assessments__assessment_grade_levels") }} as agl
            on a.assessment_id = agl.assessment_id
        where a.is_internal_assessment and a.source = 'illuminate'
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

    internal_assessments as (
        select
            a.source,
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

            ssa.student_id as illuminate_student_id,

            s.local_student_id as student_number,

            ce.powerschool_school_id,
            ce.cc_dateenrolled,
            ce.cc_dateleft,
            ce.discipline,
            ce.cc_dcid,

            ce._dbt_source_project as cc_source_project,
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
            on s.local_student_id = ce.student_number
            and a.region = ce.region
            and a.subject_area = ce.subject_area
            and a.administered_at between ce.cc_dateenrolled and ce.cc_dateleft
            and not ce.is_advanced_math_student
        where a.grade_level_id <= 9

        union all

        select
            a.source,
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

            ce.grade_level_id,

            a.canonical_assessment_id,

            s.student_id as illuminate_student_id,

            ce.student_number,
            ce.powerschool_school_id,
            ce.cc_dateenrolled,
            ce.cc_dateleft,
            ce.discipline,
            ce.cc_dcid,

            ce._dbt_source_project as cc_source_project,
        from assessment_region_scaffold as a
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on a.subject_area = ce.subject_area
            and a.region = ce.region
            and a.administered_at between ce.cc_dateenrolled and ce.cc_dateleft
        inner join
            {{ ref("stg_illuminate__public__students") }} as s
            on ce.student_number = s.local_student_id
            and ce.grade_level_id >= 10
    ),

    internal_assessments_ranked as (
        /* we need to join to `int_assessments__course_enrollments` according to
        enrollment dates, but some students have multiple enrollments for the same
        course */
        select
            *,

            row_number() over (
                partition by source, assessment_id, illuminate_student_id
                order by cc_dateleft desc, cc_dateenrolled desc
            ) as rn,
        from internal_assessments
    ),

    internal_assessments_deduped as (
        select
            source,
            assessment_id,
            title,
            administered_at,
            performance_band_set_id,
            academic_year_clean,
            subject_area,
            scope,
            module_type,
            module_code,
            region,
            grade_level_id,
            canonical_assessment_id,
            illuminate_student_id,
            student_number,
            powerschool_school_id,
            cc_dateenrolled,
            cc_dateleft,
            discipline,
            cc_dcid,
            cc_source_project,
        from internal_assessments_ranked
        where rn = 1
    ),

    apex_tested as (
        select
            r.student_number,
            r.session_id,
            r.date_taken,
            r._dbt_source_project,

            a.source,
            a.assessment_id,
            a.title,
            a.subject_area,
            a.academic_year_clean,
            a.administered_at,
            a.performance_band_set_id,
            a.scope,
            a.module_type,
            a.module_code,
            a.canonical_assessment_id,
        from {{ ref("int_focus__apex_results") }} as r
        inner join
            {{ ref("int_assessments__assessments_members") }} as a
            on r.assessment_id = a.assessment_id
        where
            r.response_type = 'overall'
            and a.source = 'apex'
            -- keep in step with int_assessments__assessments_members
            and r.academic_year >= 2026
    ),

    -- section fields are kept only when exactly 1 section matches
    apex_sections as (
        select
            t.student_number,
            t.assessment_id,

            count(distinct ce.cc_dcid) as n_sections,

            if(count(distinct ce.cc_dcid) = 1, any_value(ce.cc_dcid), null) as cc_dcid,
            if(
                count(distinct ce.cc_dcid) = 1, any_value(ce._dbt_source_project), null
            ) as cc_source_project,
            if(
                count(distinct ce.cc_dcid) = 1, any_value(ce.discipline), null
            ) as discipline,
            if(
                count(distinct ce.cc_dcid) = 1,
                any_value(ce.powerschool_school_id),
                null
            ) as powerschool_school_id,
            if(
                count(distinct ce.cc_dcid) = 1, any_value(ce.grade_level_id), null
            ) as grade_level_id,
            if(
                count(distinct ce.cc_dcid) = 1, any_value(ce.cc_dateenrolled), null
            ) as cc_dateenrolled,
            if(
                count(distinct ce.cc_dcid) = 1, any_value(ce.cc_dateleft), null
            ) as cc_dateleft,
        from apex_tested as t
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on t.student_number = ce.student_number
            and t.subject_area = ce.subject_area
            and t._dbt_source_project = ce._dbt_source_project
            and t.date_taken >= ce.cc_dateenrolled
            and t.date_taken < ce.cc_dateleft
        where ce.cc_dcid is not null
        group by t.student_number, t.assessment_id
    ),

    -- school and grade fallback when no single section matches
    apex_enrollments as (
        select
            t.student_number,
            t.assessment_id,

            se.schoolid,

            se.grade_level + 1 as grade_level_id,
        from apex_tested as t
        inner join
            {{ ref("int_extracts__student_enrollments") }} as se
            on t.student_number = se.student_number
            and t._dbt_source_project = se._dbt_source_project
            and t.date_taken >= se.entrydate
            and t.date_taken < se.exitdate
    )

select
    ia.illuminate_student_id,
    ia.student_number,
    ia.source,
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
    ia.cc_source_project,
    ia.cc_dateenrolled,
    ia.cc_dateleft,

    concat('kipp', lower(ia.region)) as _dbt_source_project,
    ia.canonical_assessment_id,

    sa.student_assessment_id,
    sa.date_taken,

    true as is_internal_assessment,
    false as is_replacement,

    cast(null as string) as section_match_method,
from internal_assessments_deduped as ia
left join
    {{ ref("stg_illuminate__dna_assessments__students_assessments") }} as sa
    on ia.illuminate_student_id = sa.student_id
    and ia.assessment_id = sa.assessment_id

union all

select
    sa.student_id as illuminate_student_id,

    s.local_student_id as student_number,

    a.source,
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
    cast(null as string) as cc_source_project,
    cast(null as date) as cc_dateenrolled,
    cast(null as date) as cc_dateleft,

    concat('kipp', lower(str.region)) as _dbt_source_project,

    a.canonical_assessment_id,

    sa.student_assessment_id,
    sa.date_taken,

    true as is_internal_assessment,
    true as is_replacement,

    cast(null as string) as section_match_method,
from {{ ref("int_assessments__assessments_members") }} as a
inner join
    {{ ref("stg_illuminate__dna_assessments__students_assessments") }} as sa
    on a.assessment_id = sa.assessment_id
inner join
    {{ ref("stg_illuminate__public__students") }} as s on sa.student_id = s.student_id
inner join
    {{ ref("int_illuminate__student_session_aff") }} as ssa
    on sa.student_id = ssa.student_id
    and a.academic_year = ssa.academic_year
    and a.tagged_grade_level_id != ssa.grade_level_id
    and ssa.rn_student_session_desc = 1
left join school_to_region as str on ssa.site_id = str.powerschool_school_id
where
    a.is_internal_assessment
    and a.source = 'illuminate'
    and a.subject_area in ('Text Study', 'Mathematics', 'Social Studies', 'Science')
    -- grade_level_id 9 = grade 8 (grade level = grade_level_id - 1)
    and a.grade_level_id <= 9

union all

select
    sa.student_id as illuminate_student_id,

    s.local_student_id as student_number,

    a.source,
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
    cast(null as string) as cc_source_project,
    cast(null as date) as cc_dateenrolled,
    cast(null as date) as cc_dateleft,

    concat('kipp', lower(str.region)) as _dbt_source_project,

    a.canonical_assessment_id,

    sa.student_assessment_id,
    sa.date_taken,

    false as is_internal_assessment,
    false as is_replacement,

    cast(null as string) as section_match_method,
from {{ ref("int_assessments__assessments_members") }} as a
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

union all

select
    cast(null as int64) as illuminate_student_id,

    t.student_number,
    t.source,
    t.assessment_id,
    t.title,
    t.subject_area,
    t.academic_year_clean as academic_year,
    t.administered_at,
    t.performance_band_set_id,

    coalesce(sc.powerschool_school_id, ae.schoolid) as powerschool_school_id,

    'Miami' as region,

    coalesce(sc.grade_level_id, ae.grade_level_id) as grade_level_id,

    t.scope,
    t.module_type,
    t.module_code,

    sc.discipline,
    sc.cc_dcid,
    sc.cc_source_project,
    sc.cc_dateenrolled,
    sc.cc_dateleft,

    t._dbt_source_project,

    t.canonical_assessment_id,
    t.session_id as student_assessment_id,
    t.date_taken,

    true as is_internal_assessment,
    false as is_replacement,

    case
        when sc.n_sections is null
        then 'none'
        when sc.n_sections = 1
        then 'single'
        else 'multiple'
    end as section_match_method,
from apex_tested as t
left join
    apex_sections as sc
    on t.student_number = sc.student_number
    and t.assessment_id = sc.assessment_id
left join
    apex_enrollments as ae
    on t.student_number = ae.student_number
    and t.assessment_id = ae.assessment_id
