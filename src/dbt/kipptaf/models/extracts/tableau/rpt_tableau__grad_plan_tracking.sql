with
    gpprogress_grades as (
        select
            gp._dbt_source_relation,
            gp.plan_id,
            gp.plan_name,
            gp.discipline_id,
            gp.discipline_name,
            gp.subject_id,
            gp.subject_name,
            gp.plan_credit_capacity,
            gp.discipline_credit_capacity,
            gp.subject_credit_capacity,

            sg.academic_year,
            sg.schoolname,
            sg.studentid,
            sg.teacher_name,
            sg.course_number,
            sg.course_name,
            sg.sectionid,
            sg.credit_type,
            sg.grade as letter_grade,
            sg.potentialcrhrs as official_potential_credits,
            sg.potentialcrhrs as potential_credits,
            sg.earnedcrhrs as earned_credits,
            sg.is_transfer_grade,

            'Earned' as credit_status,
        from {{ ref("int_powerschool__gpnode") }} as gp
        inner join
            {{ ref("stg_powerschool__storedgrades") }} as sg
            on gp.storedgradesdcid = sg.dcid
            and {{ union_dataset_join_clause(left_alias="gp", right_alias="sg") }}
            and sg.storecode = 'Y1'

        union all

        select
            gp._dbt_source_relation,
            gp.plan_id,
            gp.plan_name,
            gp.discipline_id,
            gp.discipline_name,
            gp.subject_id,
            gp.subject_name,
            gp.plan_credit_capacity,
            gp.discipline_credit_capacity,
            gp.subject_credit_capacity,

            fg.academic_year,
            fg.school_name as schoolname,
            fg.studentid,
            fg.teacher_lastfirst as teacher_name,
            fg.course_number,
            fg.course_name,
            fg.sectionid,
            fg.credittype as credit_type,
            fg.y1_letter_grade_adjusted as letter_grade,
            fg.courses_credit_hours as official_potential_credits,

            gp.enrolledcredits as potential_credits,

            if(
                fg.y1_letter_grade not like 'F%', gp.enrolledcredits, 0.0
            ) as earned_credits,

            false as is_transfer_grade,
            'Enrolled' as credit_status,
        from {{ ref("int_powerschool__gpnode") }} as gp
        inner join
            {{ ref("base_powerschool__final_grades") }} as fg
            on gp.ccdcid = fg.cc_dcid
            and {{ union_dataset_join_clause(left_alias="gp", right_alias="fg") }}
            and fg.termbin_is_current
    )

select
    e._dbt_source_relation,
    e.academic_year,
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
    e.ada,
    e.ada_above_or_at_80,
    e.advisory,

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
from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    gpprogress_grades as g
    on e.studentid = g.studentid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="g") }}
    and g.plan_name in ('NJ State Diploma', 'HS Distinction Diploma')
left join
    gpprogress_grades as sp
    on g.studentid = sp.studentid
    and g.plan_id = sp.id
    and {{ union_dataset_join_clause(left_alias="g", right_alias="sp") }}
    and sp.degree_plan_section = 'plan'
left join
    gpprogress_grades as sd
    on g.studentid = sd.studentid
    and g.discipline_id = sd.id
    and {{ union_dataset_join_clause(left_alias="g", right_alias="sd") }}
    and sd.degree_plan_section = 'discipline'
left join
    gpprogress_grades as ss
    on g.studentid = ss.studentid
    and g.subject_id = ss.id
    and {{ union_dataset_join_clause(left_alias="g", right_alias="ss") }}
    and ss.degree_plan_section = 'subject'
left join
    {{ ref("int_students__athletic_eligibility") }} as ae
    on e.studentid = ae.studentid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="ae") }}
where
    e.academic_year = {{ var("current_academic_year") }}
    and e.enroll_status = 0
    and e.grade_level >= 9
