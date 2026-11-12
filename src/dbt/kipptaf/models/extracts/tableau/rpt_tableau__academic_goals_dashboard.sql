select
    co.academic_year,
    co.region,
    co.schoolid,
    co.school,
    co.grade_level,
    co.student_number,
    co.student_name,
    co.iep_status,
    co.team as homeroom_section,
    co.advisor_lastfirst as homeroom_teacher_name,
    co.course_section_number as course_section,
    co.course_teacher_lastfirst as course_teacher_name,
    co.iready_subject as `subject`,
    co.nj_student_tier as student_tier,
    co.bucket_store,
    co.is_exempt_state_testing,

    gb.performance_level,
    gb.scale_score,
    gb.scale_score_state,
    gb.is_proficient_int_state,
    gb.scale_score_iready,
    gb.is_proficient_int as is_proficient_live_int,
    gb.is_approaching_int as is_approaching_live_int,
    gb.is_below_int as is_below_live_int,

    g.grade_goal,
    g.school_goal,
    g.region_goal,
    g.organization_goal,
    g.grade_band_goal,
    g.assessment_band_goal,

    coalesce(gb.benchmark_assessment_type, 'Untested') as benchmark_assessment_type,
    coalesce(gb.is_tested_int, 0) as is_tested_int,

    if(
        co.is_exempt_state_testing or co.is_algebra_i_ms, 0, 1
    ) as is_enrolled_denominator_int,

    case
        when co.is_exempt_state_testing
        then 'Exempt from state testing'
        when co.is_algebra_i_ms
        then format('Grade %d Algebra I', co.grade_level)
    end as denominator_exclusion,
from {{ ref("int_extracts__student_enrollments_subjects") }} as co
left join
    {{ ref("int_assessments__goal_benchmarks") }} as gb
    on co._dbt_source_project = gb._dbt_source_project
    and co.student_number = gb.student_number
    and co.academic_year = gb.academic_year
    and co.iready_subject = gb.subject
left join
    {{ ref("int_assessments__academic_goals") }} as g
    on co.schoolid = g.school_id
    and co.academic_year = g.academic_year
    and co.grade_level = g.grade_level
    and co.illuminate_subject_area = g.illuminate_subject_area
where co.academic_year >= 2026 and co.rn_year = 1 and co.enroll_status = 0
