with
    ae_status as (
        select
            _dbt_source_relation,
            studentid,
            season,
            q1_ae_status,
            q2_ae_status,
            q3_ae_status,
            q4_ae_status,
        from
            {{ ref("int_students__athletic_eligibility") }} pivot (
                max(eligibility) for quarter in (
                    'Q1' as q1_ae_status,
                    'Q2' as q2_ae_status,
                    'Q3' as q3_ae_status,
                    'Q4' as q4_ae_status
                )
            )
    )

select
    g._dbt_source_relation,
    g.academic_year,
    g.studentsdcid,
    g.plan_id,
    g.plan_name,
    g.discipline_id,
    g.discipline_name,
    g.subject_id,
    g.subject_name,
    g.teacher_name,
    g.course_number,
    g.course_name,
    g.sectionid,
    g.credit_type,
    g.letter_grade,
    g.is_transfer_grade,
    g.credit_status,
    g.earned_credits,
    g.potential_credits,

    e.region,
    e.schoolid,
    e.school,
    e.studentid,
    e.state_studentnumber,
    e.salesforce_id,
    e.student_number,
    e.student_name,
    e.grade_level,
    e.student_email,
    e.enroll_status,
    e.cohort,
    e.gender,
    e.ethnicity,
    e.dob,
    e.lunch_status,
    e.lep_status,
    e.gifted_and_talented,
    e.iep_status,
    e.is_504,
    e.is_homeless,
    e.is_out_of_district,
    e.is_self_contained,
    e.is_counseling_services,
    e.is_student_athlete,
    e.is_tutoring,
    e.year_in_network,
    e.has_fafsa,
    e.college_match_gpa,
    e.college_match_gpa_bands,
    e.contact_owner_name,
    e.ktc_cohort,
    e.ms_attended,
    e.hos,
    e.`ada`,
    e.ada_above_or_at_80,
    e.advisory,

    sp.requiredcredits as plan_required_credits,
    sp.enrolledcredits as plan_enrolled_credits,
    sp.requestedcredits as plan_requested_credits,
    sp.earnedcredits as plan_earned_credits,
    sp.waivedcredits as plan_waived_credits,

    sd.requiredcredits as discipline_required_credits,
    sd.enrolledcredits as discipline_enrolled_credits,
    sd.requestedcredits as discipline_requested_credits,
    sd.earnedcredits as discipline_earned_credits,
    sd.waivedcredits as discipline_waived_credits,

    ss.requiredcredits as subject_required_credits,
    ss.enrolledcredits as subject_enrolled_credits,
    ss.requestedcredits as subject_requested_credits,
    ss.earnedcredits as subject_earned_credits,
    ss.waivedcredits as subject_waived_credits,

    ae.q1_ae_status,
    ae.q2_ae_status,
    ae.q3_ae_status,
    ae.q4_ae_status,
from {{ ref("int_powerschool__gpprogress_grades") }} as g
inner join
    {{ ref("int_extracts__student_enrollments") }} as e
    on g.studentsdcid = e.students_dcid
    and {{ union_dataset_join_clause(left_alias="g", right_alias="e") }}
    and e.enroll_status = 0
    and e.academic_year = {{ var("current_academic_year") }}
left join
    {{ ref("int_powerschool__gpnode_unpivot") }} as sp
    on g.studentsdcid = sp.studentsdcid
    and g.plan_id = sp.id
    and {{ union_dataset_join_clause(left_alias="g", right_alias="sp") }}
    and sp.degree_plan_section = 'plan'
left join
    {{ ref("int_powerschool__gpnode_unpivot") }} as sd
    on g.studentsdcid = sd.studentsdcid
    and g.discipline_id = sd.id
    and {{ union_dataset_join_clause(left_alias="g", right_alias="sd") }}
    and sd.degree_plan_section = 'discipline'
left join
    {{ ref("int_powerschool__gpnode_unpivot") }} as ss
    on g.studentsdcid = ss.studentsdcid
    and g.subject_id = ss.id
    and {{ union_dataset_join_clause(left_alias="g", right_alias="ss") }}
    and ss.degree_plan_section = 'subject'
left join
    ae_status as ae
    on e.studentid = ae.studentid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="ae") }}
where g.plan_name in ('NJ State Diploma', 'HS Distinction Diploma')
