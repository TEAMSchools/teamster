with
    subjects as (
        select 'Reading' as iready_subject, 'ENG' as ps_credittype,
        union all
        select 'Math' as iready_subject, 'MATH' as ps_credittype,
    )
select
    co.student_number,
    co.lastfirst as student_name,
    co.grade_level,
    co.school_abbreviation as school,
    co.lep_status,
    co.gender,
    co.ethnicity as race_ethnicity,
    co.advisory_name as advisory,
    co.spedlep as iep_status,

    subj.iready_subject,
    subj.ps_credittype,

    ar as administration_round,

    e.courses_course_name as course_name,
    e.sections_section_number as section_number,
    e.teacher_lastfirst as teacher_name,

    ir.start_date,
    ir.completion_date,
    ir.rush_flag,
    ir.overall_relative_placement,
    ir.placement_3_level,
    ir.overall_scale_score,
    ir.percent_progress_to_annual_typical_growth_percent as progress_to_typical,
    ir.percent_progress_to_annual_stretch_growth_percent as progress_to_stretch,

    up.domain_name,
    up.relative_placement,
from {{ ref("base_powerschool__student_enrollments") }} as co
cross join subjects as subj
cross join unnest(['BOY', 'MOY', 'EOY']) as ar
left join
    {{ ref("base_powerschool__course_enrollments") }} as e
    on co.student_number = e.students_student_number
    and co.academic_year = e.cc_academic_year
    and subj.ps_credittype = e.courses_credittype
    and not e.is_dropped_section
    and e.rn_credittype_year = 1
left join
    {{ ref("base_iready__diagnostic_results") }} as ir
    on co.student_number = ir.student_id
    and co.academic_year = ir.academic_year_int
    and subj.iready_subject = ir.subject
    and ar = ir.test_round
    and ir.rn_subj_round = 1
left join
    {{ ref("int_iready__domain_unpivot") }} as up
    on ir.student_id = up.student_id
    and ir.academic_year_int = up.academic_year_int
    and ir.subject = up.subject
    and ir.start_date = up.start_date
    and ir.completion_date = up.completion_date
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and co.enroll_status = 0
    and co.region = 'Miami'
    and co.grade_level < 3
