with
    plans as (
        select
            p.*,

            s.studentsdcid,
            s.plan_enrolled_credits,

            s.isadvancedplan,
            s.plan_enrolled_credits,
            s.discipline_required_credits,
            s.discipline_earned_credits,
            s.discipline_enrolled_credits,
            s.discipline_requested_credits,
            s.discipline_waived_credits,

            s.subject_required_credits,
            s.subject_earned_credits,
            s.subject_enrolled_credits,
            s.subject_requested_credits,
            s.subject_waived_credits,

        from {{ ref("int_powerschool__grad_plans") }} as p
        inner join
            {{ ref("int_powerschool__grad_plans_progress_students") }} as s
            on p.plan_id = s.plan_id
            and p.subject_id = s.subject_id
            and {{ union_dataset_join_clause(left_alias="p", right_alias="s") }}
        where p.plan_name in ('NJ State Diploma', 'HS Distinction Diploma')
    )

select
    e._dbt_source_relation,
    e.academic_year,
    e.academic_year_display,
    e.district,
    e.schoolid,
    e.region,
    e.school,
    e.studentid,
    e.students_dcid,
    e.student_number,
    e.state_studentnumber,
    e.salesforce_id,
    e.student_name,
    e.student_first_name,
    e.student_last_name,
    e.grade_level,
    e.enroll_status,
    e.student_email,
    e.cohort,
    e.ktc_cohort,
    e.gender,
    e.ethnicity,
    e.lep_status,
    e.iep_status,
    e.gifted_and_talented,
    e.is_504,
    e.is_out_of_district,
    e.is_self_contained,
    e.is_counseling_services,
    e.is_student_athlete,
    e.advisory,
    e.college_match_gpa,
    e.college_match_gpa_bands,

from {{ ref("int_extracts__student_enrollments") }} as e
left join
    plans as p
    on e.students_dcid = p.studentsdcid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="p") }}
where e.grade_level >= 9 and e.academic_year = {{ var("current_academic_year") }}
