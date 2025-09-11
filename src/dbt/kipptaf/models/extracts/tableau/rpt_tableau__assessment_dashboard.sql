with
    roster as (
        select
            student_number,
            student_name,
            academic_year,
            reporting_schoolid,
            region,
            grade_level,
            advisory_name,
            enroll_status,
            cohort,
            spedlep,
            lep_status,
            is_504,
            is_self_contained,
            school,
            school_level,
            advisor_teachernumber,
            hos,
            nj_student_tier,
            is_tutoring,
            territory,
            powerschool_credittype,
            illuminate_subject_area,
        from {{ ref("int_extracts__student_enrollments_subjects") }}
        where rn_year = 1 and academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    assessment_enrollments as (
        select
            asr.powerschool_student_number,
            asr.academic_year,
            asr.assessment_id,
            asr.title,
            asr.scope,
            asr.subject_area,
            asr.term_administered,
            asr.administered_at,
            asr.term_taken,
            asr.date_taken,
            asr.module_type,
            asr.module_code,
            asr.response_type,
            asr.response_type_code,
            asr.response_type_description,
            asr.response_type_root_description,
            asr.percent_correct,
            asr.is_mastery,
            asr.performance_band_label_number,
            asr.performance_band_label,
            asr.is_replacement,
            asr.is_internal_assessment,

            enr.teachernumber,
            enr.teacher_lastfirst,
            enr.courses_course_name,
            enr.courses_credittype,
            enr.sections_expression,
            enr.sections_section_number,
            enr.is_foundations,
        from {{ ref("int_assessments__response_rollup") }} as asr
        left join
            {{ ref("base_powerschool__course_enrollments") }} as enr
            on asr.powerschool_student_number = enr.students_student_number
            and asr.academic_year = enr.terms_academic_year
            and asr.subject_area = enr.illuminate_subject_area
            and enr.rn_student_year_illuminate_subject_desc = 1
            and not enr.is_dropped_section
        where asr.academic_year >= {{ var("current_academic_year") - 1 }}
    ),

    dashboard as (
        select
            co.student_number,
            co.student_name,
            co.academic_year,
            co.reporting_schoolid,
            co.region,
            co.grade_level,
            co.advisory_name,
            co.enroll_status,
            co.cohort,
            co.spedlep,
            co.lep_status,
            co.is_504,
            co.is_self_contained,
            co.school,
            co.school_level,
            co.advisor_teachernumber,
            co.hos,
            co.nj_student_tier,
            co.is_tutoring,
            co.territory,

            ae.assessment_id,
            ae.title,
            ae.scope,
            ae.subject_area,
            ae.term_administered,
            ae.administered_at,
            ae.term_taken,
            ae.date_taken,
            ae.module_type,
            ae.module_code,
            ae.response_type,
            ae.response_type_code,
            ae.response_type_description,
            ae.response_type_root_description,
            ae.percent_correct,
            ae.is_mastery,
            ae.performance_band_label_number,
            ae.performance_band_label,
            ae.is_replacement,
            ae.is_internal_assessment,
            ae.teachernumber,
            ae.teacher_lastfirst,
            ae.courses_course_name,
            ae.sections_expression,
            ae.sections_section_number,
            ae.is_foundations,
        from roster as co
        inner join
            assessment_enrollments as ae
            on co.student_number = ae.powerschool_student_number
            and co.academic_year = ae.academic_year
            and co.powerschool_credittype = ae.courses_credittype
        where co.grade_level >= 9

        union all

        select
            co.student_number,
            co.student_name,
            co.academic_year,
            co.reporting_schoolid,
            co.region,
            co.grade_level,
            co.advisory_name,
            co.enroll_status,
            co.cohort,
            co.spedlep,
            co.lep_status,
            co.is_504,
            co.is_self_contained,
            co.school,
            co.school_level,
            co.advisor_teachernumber,
            co.hos,
            co.nj_student_tier,
            co.is_tutoring,
            co.territory,

            ae.assessment_id,
            ae.title,
            ae.scope,
            ae.subject_area,
            ae.term_administered,
            ae.administered_at,
            ae.term_taken,
            ae.date_taken,
            ae.module_type,
            ae.module_code,
            ae.response_type,
            ae.response_type_code,
            ae.response_type_description,
            ae.response_type_root_description,
            ae.percent_correct,
            ae.is_mastery,
            ae.performance_band_label_number,
            ae.performance_band_label,
            ae.is_replacement,
            ae.is_internal_assessment,
            ae.teachernumber,
            ae.teacher_lastfirst,
            ae.courses_course_name,
            ae.sections_expression,
            ae.sections_section_number,
            ae.is_foundations,
        from roster as co
        inner join
            assessment_enrollments as ae
            on co.student_number = ae.powerschool_student_number
            and co.academic_year = ae.academic_year
            and co.illuminate_subject_area = ae.subject_area
        where co.grade_level <= 9
    )

select
    student_number,
    student_name as lastfirst,
    academic_year,
    region,
    territory,
    school_level,
    reporting_schoolid as schoolid,
    school,
    grade_level,
    advisory_name as team,
    enroll_status,
    cohort,
    spedlep as iep_status,
    lep_status,
    is_504 as c_504_status,
    is_self_contained as is_pathways,
    hos as head_of_school,
    nj_student_tier,
    is_tutoring as tutoring_nj,

    assessment_id,
    title,
    scope,
    subject_area,
    term_administered,
    administered_at,
    term_taken,
    date_taken,
    module_type,
    module_code as module_number,
    response_type,
    response_type_code as standard_code,
    response_type_description as standard_description,
    response_type_root_description as domain_description,
    percent_correct,
    is_mastery,
    performance_band_label_number as performance_band_number,
    performance_band_label,
    is_replacement,
    is_internal_assessment as is_normed_scope,
    advisor_teachernumber as hr_teachernumber,
    teachernumber as enr_teachernumber,
    teacher_lastfirst as teacher_name,
    courses_course_name as course_name,
    sections_expression as expression,
    sections_section_number as section_number,
    is_foundations,

    /* retired fields kept for tableau compatibility */
    null as power_standard_goal,
    null as is_power_standard,
    null as standard_domain,
from dashboard
