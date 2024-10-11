select
    e.student_number as sis_student_id,
    e.state_studentnumber as state_student_id,
    e.student_name,
    e.dob as birthdate,
    e.schoolid as sis_school_id,
    e.school_name,
    a.assessment_name as test_name,
    'End of Grade' as test_type,
    a.discipline as test_subject_category,
    a.subject as test_subject_name,
    if(a.assessment_name = 'NJGPA', 11, a.test_grade) as test_grade_level,
    if(a.period = 'FallBlock', 'Fall', a.period) as test_period,
    a.testscalescore as scale_score,
    a.testperformancelevel as profiency_level_code,
    a.testperformancelevel_text as proficiency_level_name,
    1 as included_in_school_accountabilty,
from {{ ref("int_pearson__all_assessments") }} as a
inner join
    {{ ref("int_tableau__student_enrollments") }} as e
    on a.academic_year = e.academic_year
    and a.statestudentidentifier = e.state_studentnumber
where a.academic_year = 2023

union all

select
    e.student_number as sis_student_id,
    e.state_studentnumber as state_student_id,
    e.student_name,
    e.dob as birthdate,
    e.schoolid as sis_school_id,
    e.school_name,
    if(a.assessment_name = 'Science', 'FAST Science', a.assessment_name) as test_name,
    if(a.assessment_name != 'EOC', 'End of Grade', 'End of Course') as test_type,
    a.discipline as test_subject_category,
    a.assessment_subject as test_subject_name,
    safe_cast(a.assessment_grade as int) as test_grade_level,
    a.season as test_period,
    a.scale_score,
    a.performance_level as profiency_level_code,
    a.achievement_level as proficiency_level_name,
    1 as included_in_school_accountabilty,
from {{ ref("int_fldoe__all_assessments") }} as a
inner join
    {{ ref("int_tableau__student_enrollments") }} as e
    on a.academic_year = e.academic_year
    and a.student_id = e.state_studentnumber
where a.academic_year = 2023
