select
    co.student_number,
    co.lastfirst,
    co.academic_year,
    co.reporting_schoolid as schoolid,
    co.region,
    co.grade_level,
    co.advisory_name as team,
    co.enroll_status,
    co.cohort,
    co.spedlep as iep_status,
    co.lep_status,
    co.is_504 as c_504_status,
    co.is_self_contained as is_pathways,

    asr.assessment_id,
    asr.title,
    asr.scope,
    asr.subject_area,
    asr.term_administered,
    asr.administered_at,
    asr.term_taken,
    asr.date_taken,
    asr.module_type,
    asr.module_number,
    asr.response_type,
    asr.response_type_code as standard_code,
    asr.response_type_description as standard_description,
    asr.response_type_root_description as domain_description,
    asr.percent_correct,
    asr.is_mastery,
    asr.performance_band_label_number as performance_band_number,
    asr.performance_band_label,
    asr.is_replacement,
    asr.is_internal_assessment as is_normed_scope,

    hr.teachernumber as hr_teachernumber,

    enr.teachernumber as enr_teachernumber,
    enr.teacher_lastfirst as teacher_name,
    enr.courses_course_name as course_name,
    enr.sections_expression as expression,
    enr.sections_section_number as section_number,
    enr.is_foundations,

    sf.nj_student_tier,
    sf.tutoring_nj,

    lc.head_of_school_preferred_name_lastfirst as head_of_school,

    {# retired fields kept for tableau compatibility #}
    null as power_standard_goal,
    null as is_power_standard,
    null as standard_domain,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("int_assessments__response_rollup") }} as asr
    on co.student_number = asr.powerschool_student_number
    and co.academic_year = asr.academic_year
left join
    {{ ref("base_powerschool__course_enrollments") }} as enr
    on co.studentid = enr.cc_studentid
    and co.yearid = enr.cc_yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="enr") }}
    and asr.subject_area = enr.illuminate_subject_area
    and not enr.is_dropped_section
    and enr.rn_student_year_illuminate_subject_desc = 1
left join
    {{ ref("base_powerschool__course_enrollments") }} as hr
    on co.student_number = hr.cc_studentid
    and co.yearid = hr.cc_yearid
    and co.schoolid = hr.cc_schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="hr") }}
    and hr.cc_course_number = 'HR'
    and not hr.is_dropped_section
    and hr.rn_course_number_year = 1
left join
    {{ ref("int_reporting__student_filters") }} as sf
    on co.student_number = sf.student_number
    and co.academic_year = sf.academic_year
    and asr.subject_area = sf.illuminate_subject_area
left join
    {{ ref("int_people__leadership_crosswalk") }} as lc
    on co.schoolid = lc.home_work_location_powerschool_school_id
where
    co.academic_year >= {{ var("current_academic_year") }} - 1
    and co.rn_year = 1
    and co.grade_level != 99
