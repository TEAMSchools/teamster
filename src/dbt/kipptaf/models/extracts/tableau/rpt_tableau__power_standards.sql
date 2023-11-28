with
    ps_identifiers as (
        -- ES/MS current quarter
        select
            co.academic_year,
            co.student_number,
            co.state_studentnumber,
            co.lastfirst as student_name,
            co.advisory_name,
            co.region,
            co.school_level,
            co.school_abbreviation,
            co.schoolid,
            co.grade_level,
            co.spedlep as iep_status,

            enr.teacher_lastfirst,
            enr.sections_section_number as section_number,

            asr.subject_area,
            asr.title as assessment_name,
            asr.scope,
            asr.administered_at,
            asr.term_administered,
            asr.date_taken,
            asr.response_type_code as standard_code,
            asr.response_type_description as standard_description,
            asr.performance_band_label_number,
            asr.is_mastery,

            coalesce(asr.module_type, 'PSP') as test_number,
            (
                case
                    when asr.performance_band_label_number < 3
                    then 1
                    when asr.performance_band_label_number = 3
                    then 2
                    when asr.performance_band_label_number > 3
                    then 3
                end
            ) as growth_band,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("int_assessments__response_rollup") }} as asr
            on co.student_number = asr.powerschool_student_number
            and co.academic_year = asr.academic_year
            and asr.scope in (
                'Power Standard Pre Quiz',
                'Cumulative Review Quizzes',
                'Cold Read Quizzes',
                'Mid-quarter quiz',
                'CMA - End-of-Module'
            )
            and asr.response_type = 'standard'
            and not asr.is_replacement
        left join
            {{ ref("base_powerschool__course_enrollments") }} as enr
            on co.studentid = enr.cc_studentid
            and co.yearid = enr.cc_yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="enr") }}
            and asr.subject_area = enr.illuminate_subject_area
            and not enr.is_dropped_section
            and enr.rn_student_year_illuminate_subject_desc = 1
        inner join
            {{ ref("stg_assessments__qbls_power_standards") }} as ps
            on (
                asr.subject_area = ps.illuminate_subject_area
                and asr.term_administered = ps.term_name
                and asr.academic_year = ps.academic_year
                and co.grade_level = ps.grade_level
                and asr.response_type_code = ps.standard_code
                and ps.is_power_standard
            )
        where
            co.academic_year = {{ var("current_academic_year") }}
            and co.rn_year = 1
            and (co.grade_level between 0 and 8)
            and co.enroll_status = 0
            and co.region != 'Miami'
            and not co.is_self_contained
        union all
        -- HS current quarter
        select
            co.academic_year,
            co.student_number,
            co.state_studentnumber,
            co.lastfirst as student_name,
            co.advisory_name,
            co.region,
            co.school_level,
            co.school_abbreviation,
            co.schoolid,
            co.grade_level,
            co.spedlep as iep_status,

            enr.teacher_lastfirst,
            enr.sections_section_number as section_number,

            asr.subject_area,
            asr.title as assessment_name,
            asr.scope,
            asr.administered_at,
            asr.term_administered,
            asr.date_taken,
            asr.response_type_code as standard_code,
            asr.response_type_description as standard_description,
            asr.performance_band_label_number,
            asr.is_mastery,

            coalesce(asr.module_type, 'PSP') as test_number,
            (
                case
                    when asr.performance_band_label_number = 1
                    then 1
                    when asr.performance_band_label_number = 2
                    then 2
                    when asr.performance_band_label_number > 2
                    then 3
                end
            ) as growth_band,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("int_assessments__response_rollup") }} as asr
            on co.student_number = asr.powerschool_student_number
            and co.academic_year = asr.academic_year
            and co.academic_year = asr.academic_year
            and asr.scope
            in ('Power Standard Pre Quiz', 'HS Unit Quiz', 'Midterm or Final')
            and asr.response_type = 'standard'
            and not asr.is_replacement
        left join
            {{ ref("base_powerschool__course_enrollments") }} as enr
            on co.studentid = enr.cc_studentid
            and co.yearid = enr.cc_yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="enr") }}
            and asr.subject_area = enr.illuminate_subject_area
            and not enr.is_dropped_section
            and enr.rn_student_year_illuminate_subject_desc = 1
        inner join
            {{ ref("stg_assessments__qbls_power_standards") }} as ps
            on (
                asr.subject_area = ps.illuminate_subject_area
                and asr.term_administered = ps.term_name
                and asr.academic_year = ps.academic_year
                and asr.response_type_code = ps.standard_code
                and ps.is_power_standard
            )
        where
            co.academic_year = {{ var("current_academic_year") }}
            and co.rn_year = 1
            and (co.grade_level between 9 and 12)
            and co.enroll_status = 0
            and co.region != 'Miami'
            and not co.is_self_contained
        union all
        -- ES/MS previous quarter
        select
            co.academic_year,
            co.student_number,
            co.state_studentnumber,
            co.lastfirst as student_name,
            co.advisory_name,
            co.region,
            co.school_level,
            co.school_abbreviation,
            co.schoolid,
            co.grade_level,
            co.spedlep as iep_status,

            enr.teacher_lastfirst,
            enr.sections_section_number as section_number,

            asr.subject_area,
            asr.title as assessment_name,
            asr.scope,
            asr.administered_at,
            concat(
                'Q', cast(right(asr.term_administered, 1) as int64) + 1
            ) as term_administered,
            asr.date_taken,
            asr.response_type_code as standard_code,
            asr.response_type_description as standard_description,
            asr.performance_band_label_number,
            asr.is_mastery,

            asr.module_type as test_number,
            (
                case
                    when asr.performance_band_label_number < 3
                    then 1
                    when asr.performance_band_label_number = 3
                    then 2
                    when asr.performance_band_label_number > 3
                    then 3
                end
            ) as growth_band,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("int_assessments__response_rollup") }} as asr
            on co.student_number = asr.powerschool_student_number
            and co.academic_year = asr.academic_year
            and asr.scope = 'CMA - End-of-Module'
            and asr.response_type = 'standard'
            and not asr.is_replacement
        left join
            {{ ref("base_powerschool__course_enrollments") }} as enr
            on co.studentid = enr.cc_studentid
            and co.yearid = enr.cc_yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="enr") }}
            and asr.subject_area = enr.illuminate_subject_area
            and not enr.is_dropped_section
            and enr.rn_student_year_illuminate_subject_desc = 1
        inner join
            {{ ref("stg_assessments__qbls_power_standards") }} as ps
            on (
                asr.subject_area = ps.illuminate_subject_area
                and concat('Q', cast(right(asr.term_administered, 1) as int64) + 1)
                = ps.term_name
                and asr.academic_year = ps.academic_year
                and co.grade_level = ps.grade_level
                and asr.response_type_code = ps.standard_code
                and ps.is_power_standard
            )
        where
            co.academic_year = {{ var("current_academic_year") }}
            and co.rn_year = 1
            and (co.grade_level between 0 and 8)
            and co.enroll_status = 0
            and co.region != 'Miami'
            and not co.is_self_contained
        union all
        -- HS previous
        select
            co.academic_year,
            co.student_number,
            co.state_studentnumber,
            co.lastfirst as student_name,
            co.advisory_name,
            co.region,
            co.school_level,
            co.school_abbreviation,
            co.schoolid,
            co.grade_level,
            co.spedlep as iep_status,

            enr.teacher_lastfirst,
            enr.sections_section_number as section_number,

            asr.subject_area,
            asr.title as assessment_name,
            asr.scope,
            asr.administered_at,
            concat(
                'Q', cast(right(asr.term_administered, 1) as int64) + 1
            ) as term_administered,
            asr.date_taken,
            asr.response_type_code as standard_code,
            asr.response_type_description as standard_description,
            asr.performance_band_label_number,
            asr.is_mastery,

            coalesce(asr.module_type, 'PSP') as test_number,
            (
                case
                    when asr.performance_band_label_number = 1
                    then 1
                    when asr.performance_band_label_number = 2
                    then 2
                    when asr.performance_band_label_number > 2
                    then 3
                end
            ) as growth_band,
        from {{ ref("base_powerschool__student_enrollments") }} as co
        inner join
            {{ ref("int_assessments__response_rollup") }} as asr
            on co.student_number = asr.powerschool_student_number
            and co.academic_year = asr.academic_year
            and asr.scope in ('HS Unit Quiz', 'Midterm or Final')
            and asr.response_type = 'standard'
            and not asr.is_replacement
        left join
            {{ ref("base_powerschool__course_enrollments") }} as enr
            on co.studentid = enr.cc_studentid
            and co.yearid = enr.cc_yearid
            and {{ union_dataset_join_clause(left_alias="co", right_alias="enr") }}
            and asr.subject_area = enr.illuminate_subject_area
            and not enr.is_dropped_section
            and enr.rn_student_year_illuminate_subject_desc = 1
        inner join
            {{ ref("stg_assessments__qbls_power_standards") }} as ps
            on (
                asr.subject_area = ps.illuminate_subject_area
                and concat('Q', cast(right(asr.term_administered, 1) as int64) + 1)
                = ps.term_name
                and asr.academic_year = ps.academic_year
                and asr.response_type_code = ps.standard_code
                and ps.is_power_standard
            )
        inner join
            (
                select
                    illuminate_student_id,
                    academic_year,
                    term_administered,
                    subject_area,
                    max(administered_at) as max_administration_at,
                from {{ ref("int_assessments__response_rollup") }}
                where scope in ('HS Unit Quiz', 'Midterm or Final')
                group by
                    illuminate_student_id,
                    academic_year,
                    term_administered,
                    subject_area
            ) as pq
            on asr.illuminate_student_id = pq.illuminate_student_id
            and asr.academic_year = pq.academic_year
            and asr.term_administered = pq.term_administered
            and asr.subject_area = pq.subject_area
            and asr.administered_at = pq.max_administration_at
        where
            co.academic_year = {{ var("current_academic_year") }}
            and co.rn_year = 1
            and (co.grade_level between 9 and 12)
            and co.enroll_status = 0
            and co.region != 'Miami'
            and not co.is_self_contained
    ),

    ps_data as (
        select
            academic_year,
            student_number,
            state_studentnumber,
            student_name,
            advisory_name,
            school_abbreviation,
            schoolid,
            region,
            school_level,
            grade_level,
            iep_status,
            teacher_lastfirst,
            section_number,
            subject_area,
            assessment_name,
            scope,
            test_number,
            term_administered,
            date_taken,
            standard_code,
            standard_description,
            performance_band_label_number,
            growth_band,
            is_mastery,

            row_number() over (
                partition by
                    academic_year, student_number, subject_area, term_administered
                order by administered_at asc
            ) as rn_subj_term_asc,
            row_number() over (
                partition by
                    academic_year, student_number, subject_area, term_administered
                order by administered_at desc
            ) as rn_subj_term_desc,
        from ps_identifiers
    )

select
    p.academic_year,
    p.student_number,
    p.student_name,
    p.advisory_name,
    p.school_abbreviation,
    p.schoolid,
    p.region,
    p.school_level,
    p.grade_level,
    p.iep_status,
    p.teacher_lastfirst,
    p.section_number,
    p.subject_area,
    p.assessment_name,
    p.scope,
    p.test_number,
    p.term_administered,
    p.date_taken,
    p.standard_code,
    p.standard_description,
    p.performance_band_label_number,
    p.growth_band,
    p.is_mastery,
    p.rn_subj_term_asc,
    p.rn_subj_term_desc,

    sf.nj_student_tier,
    sf.state_test_proficiency,
    sf.tutoring_nj,

    lc.head_of_school_preferred_name_lastfirst as head_of_school,

    case
        when
            max(case when p.rn_subj_term_desc = 1 then p.growth_band end) over (
                partition by
                    p.academic_year,
                    p.student_number,
                    p.subject_area,
                    p.term_administered
            ) > max(case when rn_subj_term_asc = 1 then growth_band end) over (
                partition by
                    p.academic_year,
                    p.student_number,
                    p.subject_area,
                    p.term_administered
            )
        then 'Grew'
        when
            max(case when rn_subj_term_desc = 1 then growth_band end) over (
                partition by
                    p.academic_year,
                    p.student_number,
                    p.subject_area,
                    p.term_administered
            ) = max(case when p.rn_subj_term_asc = 1 then p.growth_band end) over (
                partition by
                    p.academic_year,
                    p.student_number,
                    p.subject_area,
                    p.term_administered
            )
        then 'Maintained'
        when
            max(case when p.rn_subj_term_desc = 1 then p.growth_band end) over (
                partition by
                    p.academic_year,
                    p.student_number,
                    p.subject_area,
                    p.term_administered
            ) < max(case when rn_subj_term_asc = 1 then p.growth_band end) over (
                partition by
                    p.academic_year,
                    p.student_number,
                    p.subject_area,
                    p.term_administered
            )
        then 'Regressed'
    end as growth_status,
    max(case when p.rn_subj_term_desc = 1 then p.growth_band end) over (
        partition by
            p.academic_year, p.student_number, p.subject_area, p.term_administered
    ) as growth_band_recent,
    max(case when p.rn_subj_term_desc = 1 then p.is_mastery end) over (
        partition by
            p.academic_year, p.student_number, p.subject_area, p.term_administered
    ) as mastery_recent,
    case
        when
            max(case when p.rn_subj_term_desc = 1 then p.growth_band end) over (
                partition by
                    p.academic_year,
                    p.student_number,
                    p.subject_area,
                    p.term_administered
            ) > max(case when p.rn_subj_term_asc = 1 then p.growth_band end) over (
                partition by
                    p.academic_year,
                    p.student_number,
                    p.subject_area,
                    p.term_administered
            )
        then 1
        else 0
    end as is_growth,
    case
        when
            max(case when p.rn_subj_term_desc = 1 then p.growth_band end) over (
                partition by
                    p.academic_year,
                    p.student_number,
                    p.subject_area,
                    p.term_administered
            ) < max(case when p.rn_subj_term_asc = 1 then p.growth_band end) over (
                partition by
                    p.academic_year,
                    p.student_number,
                    p.subject_area,
                    p.term_administered
            )
        then 1
        else 0
    end as is_regress,
from ps_data as p
left join
    {{ ref("int_reporting__student_filters") }} as sf
    on p.student_number = sf.student_number
    and p.academic_year = sf.academic_year
    and p.subject_area = sf.illuminate_subject_area
left join
    {{ ref("int_people__leadership_crosswalk") }} as lc
    on p.schoolid = lc.home_work_location_powerschool_school_id
