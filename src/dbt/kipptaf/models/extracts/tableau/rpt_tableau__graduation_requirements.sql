with
    roster as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.academic_year_display,
            e.region,
            e.schoolid,
            e.school_name,
            e.school,
            e.students_dcid,
            e.studentid,
            e.state_studentnumber,
            e.student_number,
            e.student_name,
            e.student_first_name,
            e.student_last_name,
            e.grade_level,
            e.enroll_status,
            e.cohort,
            e.advisory,
            e.iep_status,
            e.is_504,
            e.lep_status,
            e.is_retained_year,
            e.is_retained_ever,
            e.student_email as student_email_google,
            e.salesforce_id as kippadb_contact_id,
            e.ktc_cohort,
            e.has_fafsa,

            s.courses_course_name,
            s.teacher_lastfirst,
            s.sections_external_expression,
            s.sections_section_number as section_number,

            discipline,

        from {{ ref("int_extracts__student_enrollments") }} as e
        left join
            {{ ref("base_powerschool__course_enrollments") }} as s
            on e.studentid = s.cc_studentid
            and e.academic_year = s.cc_academic_year
            and {{ union_dataset_join_clause(left_alias="e", right_alias="s") }}
            and s.courses_course_name like 'College and Career%'
            and s.rn_course_number_year = 1
            and not s.is_dropped_section
        cross join unnest(['Math', 'ELA']) as discipline
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.schoolid != 999999
            and e.cohort between ({{ var("current_academic_year") - 1 }}) and (
                {{ var("current_academic_year") + 5 }}
            )
    )

select distinct
    r._dbt_source_relation,
    r.academic_year,
    r.academic_year_display,
    r.region,
    r.schoolid,
    r.school_name,
    r.school,
    r.student_number,
    r.state_studentnumber,
    r.kippadb_contact_id,
    r.students_dcid,
    r.student_name,
    r.student_first_name,
    r.student_last_name,
    r.enroll_status,
    r.cohort,
    r.ktc_cohort,
    r.has_fafsa,
    r.grade_level,
    r.iep_status,
    r.is_504,
    r.lep_status,
    r.is_retained_year,
    r.is_retained_ever,
    r.student_email_google,
    r.advisory,
    r.courses_course_name as ccr_course,
    r.teacher_lastfirst as ccr_teacher,
    r.sections_external_expression as ccr_period,
    r.section_number as ccr_section_number,
    r.discipline,

    c.pathway_option,
    c.test_type,
    c.subject_area,
    c.scale_score,
    c.cutoff,
    c.met_pathway_cutoff,
    c.points_short,
    c.ps_grad_path_code,
    c.njgpa_attempt,
    c.attempted_njgpa_ela,
    c.attempted_njgpa_math,
    c.met_njgpa,
    c.met_act,
    c.met_sat,
    c.met_psat10,
    c.met_psat_nmsqt,
    c.final_grad_path_code,
    c.grad_eligibility,

from roster as r
left join
    {{ ref("int_students__graduation_path_codes") }} as c
    on r.student_number = c.student_number
    and r.discipline = c.discipline
    and c.scale_score is not null
