{{ config(enabled=False) }}
select
    enr.sectionid,
    enr.academic_year,
    enr.credittype,
    enr.course_number,
    enr.course_name,
    enr.section_number,
    enr.teacher_name,
    enr.student_number,
    enr.schoolid,
    enr.db_name,

    co.lastfirst,
    co.grade_level,
    co.iep_status,

    gb.term_abbreviation,
    gb.storecode as finalgradename,
    gb.finalgradesetuptype,
    gb.gradingformulaweightingtype,
    gb.category_name as grade_category,
    gb.category_abbreviation as grade_category_abbreviation,
    gb.weight as weighting,
    gb.includeinfinalgrades,
    left(gb.storecode, 1) as finalgrade_category,

    a1.assignmentid,
    a1.assign_date,
    a1.assign_name,
    a1.pointspossible,
    a1.weight,
    a1.extracreditpoints,
    a1.isfinalscorecalculated,

    s1.scorepoints,
    s1.islate,
    s1.isexempt,
    s1.ismissing,
from powerschool.course_enrollments_current_static as enr
inner join
    powerschool.cohort_identifiers_static as co
    on enr.student_number = co.student_number
    and enr.academic_year = co.academic_year
    and enr.db_name = co.db_name
    and co.rn_year = 1
inner join
    powerschool.gradebook_setup_static as gb
    on enr.sections_dcid = gb.sectionsdcid
    and enr.db_name = gb.db_name
    and gb.finalgradesetuptype = 'Total_Points'
left join
    powerschool.gradebook_assignments_current_static as a1
    on gb.sectionsdcid = a1.sectionsdcid
    and a1.assign_date between gb.term_start_date and gb.term_end_date
    and gb.db_name = a1.db_name
left join
    powerschool.gradebook_assignments_scores_current_static as s1
    on a1.assignmentsectionid = s1.assignmentsectionid
    and a1.db_name = s1.db_name
    and enr.students_dcid = s1.studentsdcid

union all

select
    enr.sectionid,
    enr.academic_year,
    enr.credittype,
    enr.course_number,
    enr.course_name,
    enr.section_number,
    enr.teacher_name,
    enr.student_number,
    enr.schoolid,
    enr.db_name,

    co.lastfirst,
    co.grade_level,
    co.iep_status,

    gb.term_abbreviation,
    gb.storecode as finalgradename,
    gb.finalgradesetuptype,
    gb.gradingformulaweightingtype,
    gb.category_name as grade_category,
    gb.category_abbreviation as grade_category_abbreviation,
    gb.weight as weighting,
    gb.includeinfinalgrades,
    left(gb.storecode, 1) as finalgrade_category,

    a2.assignmentid,
    a2.assign_date,
    a2.assign_name,
    a2.pointspossible,
    a2.weight,
    a2.extracreditpoints,
    a2.isfinalscorecalculated,

    s2.scorepoints,
    s2.islate,
    s2.isexempt,
    s2.ismissing,
from powerschool.course_enrollments_current_static as enr
inner join
    powerschool.cohort_identifiers_static as co
    on enr.student_number = co.student_number
    and enr.academic_year = co.academic_year
    and enr.db_name = co.db_name
    and co.rn_year = 1
inner join
    powerschool.gradebook_setup_static as gb
    on enr.sections_dcid = gb.sectionsdcid
    and enr.db_name = gb.db_name
    and gb.finalgradesetuptype != 'Total_Points'
left join
    powerschool.gradebook_assignments_current_static as a2
    on gb.sectionsdcid = a2.sectionsdcid
    and gb.assignmentcategoryid = a2.categoryid
    and a2.assign_date between gb.term_start_date and gb.term_end_date
    and gb.db_name = a2.db_name
left join
    powerschool.gradebook_assignments_scores_current_static as s2
    on a2.assignmentsectionid = s2.assignmentsectionid
    and a2.db_name = s2.db_name
    and enr.students_dcid = s2.studentsdcid
