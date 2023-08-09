select
    enr.cc_sectionid as sectionid,
    enr.cc_section_number as section_number,
    enr.cc_course_number as course_number,
    enr.courses_course_name as course_name,
    enr.courses_credittype as credittype,
    enr.teacher_lastfirst as teacher_name,
    regexp_extract(enr._dbt_source_relation, r'(kippw\+)_') as db_name,

    co.student_number,
    co.lastfirst,
    co.academic_year,
    co.schoolid,
    co.school_name
    co.grade_level,
    co.spedlep as iep_status,

    gb.term_abbreviation,
    gb.storecode as finalgradename,
    gb.grading_formula_weighting_type as finalgradesetuptype,
    gb.grading_formula_weighting_type as gradingformulaweightingtype,
    gb.category_name as grade_category,
    gb.storecode as grade_category_abbreviation,
    gb.grade_calc_formula_weight as weighting,
    gb.is_in_final_grades as includeinfinalgrades,
    left(gb.storecode, 1) as finalgrade_category,

    a.assignmentid,
    a.duedate as assign_date,
    a.name as assign_name,
    a.totalpointvalue as pointspossible,
    a.weight,
    a.extracreditpoints,
    a.iscountedinfinalgrade as isfinalscorecalculated,

    s.scorepoints,
    s.islate,
    s.isexempt,
    s.ismissing,
from {{ ref("base_powerschool__course_enrollments") }} as enr
inner join
    {{ ref("base_powerschool__student_enrollments") }} as co
    on enr.cc_studentid = co.studentid
    and enr.cc_yearid = co.yearid
    and {{ union_dataset_join_clause(left_alias="enr", right_alias="co") }}
    and co.rn_year = 1
inner join
    {{ ref("int_powerschool__section_grade_config") }} as gb
    on enr.sections_dcid = gb.sections_dcid
    and {{ union_dataset_join_clause(left_alias="enr", right_alias="gb") }}
    and gb.grading_formula_weighting_type = 'Total_Points'
left join
    {{ ref("int_powerschool__gradebook_assignments") }} as a
    on gb.sections_dcid = a.sectionsdcid
    and a.duedate between gb.term_start_date and gb.term_end_date
    and {{ union_dataset_join_clause(left_alias="gb", right_alias="a") }}
left join
    {{ ref("int_powerschool__gradebook_assignment_scores") }} as s
    on a.assignmentsectionid = s.assignmentsectionid
    and {{ union_dataset_join_clause(left_alias="a", right_alias="s") }}
    and enr.students_dcid = s.studentsdcid
where enr.cc_academic_year >= {{ var("current_academic_year") }} - 2

union all

select
    enr.cc_sectionid as sectionid,
    enr.cc_section_number as section_number,
    enr.cc_course_number as course_number,
    enr.courses_course_name as course_name,
    enr.courses_credittype as credittype,
    enr.teacher_lastfirst as teacher_name,
    regexp_extract(enr._dbt_source_relation, r'(kippw\+)_') as db_name,

    co.student_number,
    co.lastfirst,
    co.academic_year,
    co.schoolid,
    co.grade_level,
    co.spedlep as iep_status,

    gb.term_abbreviation,
    gb.storecode as finalgradename,
    gb.grading_formula_weighting_type as finalgradesetuptype,
    gb.grading_formula_weighting_type as gradingformulaweightingtype,
    gb.category_name as grade_category,
    gb.storecode as grade_category_abbreviation,
    gb.grade_calc_formula_weight as weighting,
    gb.is_in_final_grades as includeinfinalgrades,
    left(gb.storecode, 1) as finalgrade_category,

    a.assignmentid,
    a.duedate as assign_date,
    a.name as assign_name,
    a.totalpointvalue as pointspossible,
    a.weight,
    a.extracreditpoints,
    a.iscountedinfinalgrade as isfinalscorecalculated,

    s.scorepoints,
    s.islate,
    s.isexempt,
    s.ismissing,
from {{ ref("base_powerschool__course_enrollments") }} as enr
inner join
    {{ ref("base_powerschool__student_enrollments") }} as co
    on enr.cc_studentid = co.studentid
    and enr.cc_yearid = co.yearid
    and {{ union_dataset_join_clause(left_alias="enr", right_alias="co") }}
    and co.rn_year = 1
inner join
    {{ ref("int_powerschool__section_grade_config") }} as gb
    on enr.sections_dcid = gb.sections_dcid
    and {{ union_dataset_join_clause(left_alias="enr", right_alias="gb") }}
    and gb.grading_formula_weighting_type != 'Total_Points'
left join
    {{ ref("int_powerschool__gradebook_assignments") }} as a
    on gb.sections_dcid = a.sectionsdcid
    and gb.category_id = a.category_id
    and a.duedate between gb.term_start_date and gb.term_end_date
    and {{ union_dataset_join_clause(left_alias="gb", right_alias="a") }}
left join
    {{ ref("int_powerschool__gradebook_assignment_scores") }} as s
    on a.assignmentsectionid = s.assignmentsectionid
    and {{ union_dataset_join_clause(left_alias="a", right_alias="s") }}
    and enr.students_dcid = s.studentsdcid
where enr.cc_academic_year >= {{ var("current_academic_year") }} - 2
