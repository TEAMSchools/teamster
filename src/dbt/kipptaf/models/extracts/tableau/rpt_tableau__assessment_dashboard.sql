{{ config(enabled=False) }}
with
    sd_dupe_remove as (
        select
            st.standard_code,
            st.standard_domain,
            row_number() over (
                partition by st.standard_code order by st.standard_domain asc
            ) as rn_standard
        from assessments.standards_translation as st
    )

select
    co.student_number,
    co.lastfirst,
    co.academic_year,
    co.reporting_schoolid as schoolid,
    co.region,
    co.grade_level,
    co.team,
    co.enroll_status,
    co.cohort,
    co.iep_status,
    co.lep_status,
    co.c_504_status,
    co.is_pathways,

    asr.assessment_id,
    asr.title,
    asr.scope,
    asr.subject_area,
    asr.term_administered,
    asr.administered_at,
    asr.term_taken,
    asr.date_taken,
    asr.response_type,
    asr.module_type,
    asr.module_number,
    asr.standard_code,
    asr.standard_description,
    asr.domain_description,
    asr.percent_correct,
    asr.is_mastery,
    asr.performance_band_number,
    asr.performance_band_label,
    asr.is_replacement,
    asr.is_normed_scope,

    hr.teachernumber as hr_teachernumber,

    enr.teachernumber as enr_teachernumber,
    enr.teacher_name,
    enr.course_name,
    enr.expression,
    enr.section_number,

    ns.is_foundations,

    ps.goal as power_standard_goal,
    case when ps.standard_code is not null then 1 end as is_power_standard,

    sd.standard_domain,
from powerschool.cohort_identifiers_static as co
inner join
    illuminate_dna_assessments.agg_student_responses_all as asr
    on co.student_number = asr.local_student_id
    and co.academic_year = asr.academic_year
left join
    powerschool.course_enrollments as enr
    on co.student_number = enr.student_number
    and co.academic_year = enr.academic_year
    and co. [db_name] = enr. [db_name]
    and asr.subject_area = enr.illuminate_subject
    and enr.course_enroll_status = 0
    and enr.section_enroll_status = 0
    and enr.rn_illuminate_subject = 1
left join
    powerschool.course_enrollments as hr
    on co.student_number = hr.student_number
    and co.academic_year = hr.academic_year
    and co. [db_name] = hr. [db_name]
    and co.schoolid = hr.schoolid
    and hr.course_number = 'HR'
    and hr.course_enroll_status = 0
    and hr.section_enroll_status = 0
    and hr.rn_course_yr = 1
left join assessments.normed_subjects as ns on enr.course_number = ns.course_number
left join
    assessments.power_standards as ps
    on asr.assessment_id = ps.assessment_id
    and asr.standard_code = ps.standard_code
    and co.reporting_schoolid = ps.schoolid
    and co.academic_year = ps.academic_year
left join
    sd_dupe_remove as sd on asr.standard_code = sd.standard_code and sd.rn_standard = 1
where
    co.academic_year >= utilities.global_academic_year() - 1
    and co.rn_year = 1
    and co.grade_level != 99
