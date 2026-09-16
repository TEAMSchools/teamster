with
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
            s.anchor_date,

            ce.cc_dcid,
            ce._dbt_source_project as cc_source_project,
            ce.cc_dateleft,
            ce.powerschool_school_id,
            ce.region,

            1 as tier,

            'subject_section' as resolution_type,
        from {{ ref("int_assessments__score_anchors") }} as s
        inner join
            {{ ref("int_assessments__course_enrollments") }} as ce
            on s.powerschool_student_number = ce.powerschool_student_number
            and s._dbt_source_project = ce._dbt_source_project
            and s.subject_area = ce.illuminate_subject_area
            and s.anchor_date >= ce.cc_dateenrolled
            and s.anchor_date < ce.cc_dateleft
            -- only sections with a real course-enrollment row resolve to a
            -- dim_student_section_enrollments FK; synthetic ES-Writing (RHET)
            -- inventory rows carry cc_dcid = null and have no dim row
            and ce.cc_dcid is not null
    ),

    -- grain projection, not dup-masking
    resolved_subject_keys as (select distinct score_grain_key, from candidates_subject),

    scores_unresolved as (
        select s.*,
        from {{ ref("int_assessments__score_anchors") }} as s
        left join resolved_subject_keys as cs on s.score_grain_key = cs.score_grain_key
        where cs.score_grain_key is null
    ),

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
            s.anchor_date,

            ce.cc_dcid,
            ce._dbt_source_project as cc_source_project,
            ce.cc_dateleft,
            ce.powerschool_school_id,
            ce.region,

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

    all_candidates as (
        select *,
        from candidates_subject

        union all

        select *,
        from candidates_homeroom
    ),

    -- one section per score: prefer the subject section (tier 1) over homeroom,
    -- then the section that ends latest among ties within a tier
    all_candidates_ranked as (
        select
            *,

            row_number() over (
                partition by score_grain_key
                order by tier asc, cc_dateleft desc, cc_dcid desc
            ) as rn,
        from all_candidates
    ),

    resolved as (
        select
            powerschool_student_number,
            canonical_assessment_id,
            academic_year,
            administration_period,
            subject_area,
            _dbt_source_project,
            source_type,
            resolution_type,

            cc_dcid,
            cc_source_project,
            powerschool_school_id,
            region,
        from all_candidates_ranked
        where rn = 1
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

    -- the resolved section's school and region. Carried so consumers can resolve
    -- a score's reporting quarter from the score's OWN date (#4484); this model
    -- is one row per score GRAIN, so its anchor_date cannot stand in for the
    -- date of every score row sharing that grain.
    powerschool_school_id,
    region,

    {{ dbt_utils.generate_surrogate_key(["cc_dcid", "cc_source_project"]) }}
    as student_section_enrollment_key,
from resolved
