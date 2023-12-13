-- K-8
select
    co.academic_year,
    co.student_number,
    co.state_studentnumber,
    co.lastfirst as student_name,
    co.advisory_name,
    co.region,
    co.school_level,
    co.school_abbreviation,
    co.grade_level,
    co.spedlep as iep_status,

    enr.teacher_lastfirst,
    enr.sections_section_number as section_number,

    asr.subject_area,
    asr.title as assessment_name,
    asr.assessment_id,
    asr.scope,
    asr.module_type,
    asr.module_number,
    asr.term_administered,
    asr.administered_at,
    asr.response_type,
    asr.response_type_code as standard_code,
    asr.response_type_description as standard_description,
    asr.performance_band_label_number,
    asr.is_mastery,
    asr.percent_correct,

    ps.is_power_standard,
    ps.qbl,

    ag.grade_goal,
    ag.school_goal,
    ag.region_goal,
    ag.organization_goal,

    sf.bucket_two,
    sf.state_test_proficiency,
    sf.tutoring_nj,
    sf.nj_student_tier,

    lc.head_of_school_preferred_name_lastfirst as head_of_school,

    case
        when asr.is_mastery then 1 when not asr.is_mastery then 0
    end as is_mastery_int,
    case
        when co.grade_level < 3
        then 'K-2'
        when co.grade_level between 3 and 4
        then '3-4'
        when co.grade_level between 5 and 8
        then '5-8'
    end as grade_band,
    case
        when asr.performance_band_label_number < 3
        then 1
        when asr.performance_band_label_number = 3
        then 2
        when asr.performance_band_label_number > 3
        then 3
    end as performance_3_band,
    case
        when asr.response_type = 'standard'
        then
            dense_rank() over (
                partition by
                    co.academic_year,
                    co.grade_level,
                    asr.subject_area,
                    asr.term_administered
                order by asr.administered_at desc
            )
    end as rn_test_subject_term,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("int_assessments__response_rollup") }} as asr
    on co.student_number = asr.powerschool_student_number
    and co.academic_year = asr.academic_year
    and asr.module_type in ('CRQ', 'MQQ', 'QA')
    and asr.response_type in ('overall', 'standard')
    and not asr.is_replacement
left join
    {{ ref("base_powerschool__course_enrollments") }} as enr
    on co.studentid = enr.cc_studentid
    and co.yearid = enr.cc_yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="enr") }}
    and asr.subject_area = enr.illuminate_subject_area
    and not enr.is_dropped_section
    and enr.rn_student_year_illuminate_subject_desc = 1
left join
    {{ ref("stg_assessments__qbls_power_standards") }} as ps
    on asr.subject_area = ps.illuminate_subject_area
    and asr.academic_year = ps.academic_year
    and co.grade_level = ps.grade_level
    and asr.response_type_code = ps.standard_code
    and asr.term_administered = ps.term_name
left join
    {{ ref("stg_assessments__academic_goals") }} as ag
    on asr.academic_year = ag.academic_year
    and co.schoolid = ag.school_id
    and co.grade_level = ag.grade_level
    and asr.subject_area = ag.illuminate_subject_area
left join
    {{ ref("int_reporting__student_filters") }} as sf
    on sf.student_number = co.student_number
    and sf.academic_year = co.academic_year
    and asr.subject_area = sf.illuminate_subject_area
left join
    {{ ref("int_people__leadership_crosswalk") }} as lc
    on co.schoolid = lc.home_work_location_powerschool_school_id
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and (co.grade_level between 0 and 8)
    and co.enroll_status = 0
    and co.region != 'Miami'
    and not co.is_self_contained
union all

-- HS
select
    co.academic_year,
    co.student_number,
    co.state_studentnumber,
    co.lastfirst as student_name,
    co.advisory_name,
    co.region,
    co.school_level,
    co.school_abbreviation,
    co.grade_level,
    co.spedlep as iep_status,

    enr.teacher_lastfirst,
    enr.sections_section_number as section_number,

    asr.subject_area,
    asr.title as assessment_name,
    asr.assessment_id,
    asr.scope,
    asr.module_type,
    asr.module_number,
    asr.term_administered,
    asr.administered_at,
    asr.response_type,
    asr.response_type_code as standard_code,
    asr.response_type_description as standard_description,
    asr.performance_band_label_number,
    asr.is_mastery,
    asr.percent_correct,

    ps.is_power_standard,
    ps.qbl,

    ag.grade_goal,
    ag.school_goal,
    ag.region_goal,
    ag.organization_goal,

    sf.bucket_two,
    sf.state_test_proficiency,
    sf.tutoring_nj,
    sf.nj_student_tier,

    lc.head_of_school_preferred_name_lastfirst as head_of_school,

    case
        when asr.is_mastery then 1 when not asr.is_mastery then 0
    end as is_mastery_int,
    'HS' as grade_band,
    case
        when asr.performance_band_label_number < 2
        then 1
        when asr.performance_band_label_number = 2
        then 2
        when asr.performance_band_label_number > 2
        then 3
    end as performance_3_band,
    case
        when asr.response_type = 'standard'
        then
            dense_rank() over (
                partition by co.academic_year, asr.subject_area, asr.term_administered
                order by asr.administered_at desc
            )
    end as rn_test_subject_term,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("int_assessments__response_rollup") }} as asr
    on co.student_number = asr.powerschool_student_number
    and co.academic_year = asr.academic_year
    and asr.module_type in ('UQ', 'EX')
    and asr.response_type in ('overall', 'standard')
    and not asr.is_replacement
left join
    {{ ref("base_powerschool__course_enrollments") }} as enr
    on co.studentid = enr.cc_studentid
    and co.yearid = enr.cc_yearid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="enr") }}
    and asr.subject_area = enr.illuminate_subject_area
    and not enr.is_dropped_section
    and enr.rn_student_year_illuminate_subject_desc = 1
left join
    {{ ref("stg_assessments__qbls_power_standards") }} as ps
    on asr.subject_area = ps.illuminate_subject_area
    and asr.academic_year = ps.academic_year
    and asr.term_administered = ps.term_name
    and case
        when ps.parent_standard is not null
        then asr.response_type_id = ps.parent_standard
        else asr.response_type_code = ps.standard_code
    end
left join
    {{ ref("stg_assessments__academic_goals") }} as ag
    on asr.academic_year = ag.academic_year
    and co.schoolid = ag.school_id
    and asr.subject_area = ag.illuminate_subject_area
left join
    {{ ref("int_reporting__student_filters") }} as sf
    on sf.student_number = co.student_number
    and sf.academic_year = co.academic_year
    and asr.subject_area = sf.illuminate_subject_area
left join
    {{ ref("int_people__leadership_crosswalk") }} as lc
    on co.schoolid = lc.home_work_location_powerschool_school_id
where
    co.academic_year = {{ var("current_academic_year") }}
    and co.rn_year = 1
    and (co.grade_level between 9 and 12)
    and co.enroll_status = 0
    and co.region != 'Miami'
    and not co.is_self_contained
