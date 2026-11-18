-- keep in step with int_assessments__scaffold (school_to_region and the
-- replacement branch): this reads that branch before its inner join to
-- region_groups drops these sittings
select
    a.source,
    a.assessment_id,

    sa.student_assessment_id,

    ssa.site_id as powerschool_school_id,

    loc.city as region,
from {{ ref("int_assessments__assessments_members") }} as a
inner join
    {{ ref("stg_illuminate__dna_assessments__students_assessments") }} as sa
    on a.assessment_id = sa.assessment_id
inner join
    {{ ref("int_illuminate__student_session_aff") }} as ssa
    on sa.student_id = ssa.student_id
    and a.academic_year = ssa.academic_year
    and a.tagged_grade_level_id != ssa.grade_level_id
    and ssa.rn_student_session_desc = 1
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on ssa.site_id = loc.powerschool_school_id
    and not loc.is_campus
    and not loc.is_pathways
    -- the canonical mart-scope location filter (#3751 / #3754)
    and loc.location_name != 'KIPP Whittier Elementary'
left join unnest(a.region_groups) as rg on loc.city = rg.region
where
    a.is_internal_assessment
    and a.source = 'illuminate'
    and a.subject_area in ('Text Study', 'Mathematics', 'Social Studies', 'Science')
    -- grade_level_id 9 = grade 8 (grade level = grade_level_id - 1)
    and a.grade_level_id <= 9
    and rg.region is null
