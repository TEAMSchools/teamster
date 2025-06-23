with
    py_credits as (
        select
            _dbt_source_relation,
            yearid,
            studentid,

            if(sum(earnedcrhrs) >= 30, true, false) as met_py_credits,
        from {{ ref("stg_powerschool__storedgrades") }}
        where
            storecode = 'Y1' and academic_year = {{ var("current_academic_year") - 1 }}
        group by _dbt_source_relation, yearid, studentid
    ),

    cy_credits as (
        select
            _dbt_source_relation,
            yearid,
            studentid,

            if(
                sum(if(y1_letter_grade_adjusted in ('F', 'F*'), 1, 0)) = 0, true, false
            ) as met_cy_credits,
        from {{ ref("base_powerschool__final_grades") }}
        where storecode = 'Q2'
        group by _dbt_source_relation, yearid, studentid
    ),

    students as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.region,
            e.schoolid,
            e.school,
            e.studentid,
            e.studentsdcid,
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

            pyc.met_py_credits,

            cyc.met_cy_credits,

            if(
                e.grade_level = 9
                and (e.grade_level_prev < 9 or e.grade_level_prev is null),
                true,
                false
            ) as is_first_time_ninth,

            if(
                date_diff(date({{ var("current_academic_year") }}, 09, 01), e.dob, year)
                >= 19,
                false,
                true
            ) as is_age_eligible,
        from {{ ref("int_extracts__student_enrollments") }} as e
        left join
            py_credits as pyc
            on e.studentid = pyc.studentid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="pyc") }}
        left join
            cy_credits as cyc
            on e.studentid = cyc.studentid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="cyc") }}
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.enroll_status = 0
            and e.grade_level >= 9
    )

select
    e._dbt_source_relation,
    e.academic_year,
    e.region,
    e.schoolid,
    e.school,
    e.studentid,
    e.studentsdcid,
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

    case
        when not e.is_age_eligible
        then 'Ineligible - Age'
        when e.is_first_time_ninth
        then 'Eligible'
        when not e.met_py_credits
        then 'Ineligble - Credits'
        when e.met_py_credits and e.py_y1_gpa < 2.2
        then 'Ineligible - GPA'
        when e.met_py_credits and e.py_y1_ada >= 0.9 and e.py_y1_gpa >= 2.5
        then 'Eligible'
        when
            e.met_py_credits and e.py_y1_ada >= 0.9 and e.py_y1_gpa between 2.2 and 2.49
        then 'Probation - GPA'
        when e.met_py_credits and e.py_y1_ada < 0.9 and e.py_y1_gpa >= 2.5
        then 'Probation - ADA'
        when e.met_py_credits and e.py_y1_ada < 0.9 and e.py_y1_gpa between 2.2 and 2.49
        then 'Probation - ADA and GPA'
    end as q1_ae_status,

    case
        when not e.is_age_eligible
        then 'Ineligible - Age'
        when not e.met_py_credits and not e.is_first_time_ninth
        then 'Ineligble - Credits'
        when e.cy_q1_gpa < 2.2 and (e.met_py_credits or e.is_first_time_ninth)
        then 'Ineligible - GPA'
        when
            e.cy_q1_ada >= 0.9
            and e.cy_q1_gpa >= 2.5
            and (e.met_py_credits or e.is_first_time_ninth)
        then 'Eligible'
        when
            e.cy_q1_ada >= 0.9
            and e.cy_q1_gpa between 2.2 and 2.49
            and (e.met_py_credits or e.is_first_time_ninth)
        then 'Probation - GPA'
        when
            e.cy_q1_ada < 0.9
            and e.cy_q1_gpa >= 2.5
            and (e.met_py_credits or e.is_first_time_ninth)
        then 'Probation - ADA'
        when
            e.cy_q1_ada < 0.9
            and e.cy_q1_gpa between 2.2 and 2.49
            and (e.met_py_credits or e.is_first_time_ninth)
        then 'Probation - ADA and GPA'
    end as q2_ae_status,

    case
        when not e.is_age_eligible
        then 'Ineligible - Age'
        when not e.met_cy_credits
        then 'Ineligble - Credits'
        when e.met_cy_credits and e.cy_s1_gpa < 2.2
        then 'Ineligible - GPA'
        when e.met_cy_credits and e.cy_s1_ada >= 0.9 and e.cy_s1_gpa >= 2.5
        then 'Eligible'
        when
            e.met_cy_credits and e.cy_s1_ada >= 0.9 and e.cy_s1_gpa between 2.2 and 2.49
        then 'Probation - GPA'
        when e.met_cy_credits and e.cy_s1_ada < 0.9 and e.cy_s1_gpa >= 2.5
        then 'Probation - ADA'
        when e.met_cy_credits and e.cy_s1_ada < 0.9 and e.cy_s1_gpa between 2.2 and 2.49
        then 'Probation - ADA and GPA'
    end as q3_ae_status,

    case
        when not e.is_age_eligible
        then 'Ineligible - Age'
        when not e.met_cy_credits
        then 'Ineligble - Credits'
        when e.met_cy_credits and e.cy_s1_gpa < 2.2
        then 'Ineligible - GPA'
        when e.met_cy_credits and e.cy_s1_ada >= 0.9 and e.cy_s1_gpa >= 2.5
        then 'Eligible'
        when
            e.met_cy_credits and e.cy_s1_ada >= 0.9 and e.cy_s1_gpa between 2.2 and 2.49
        then 'Probation - GPA'
        when e.met_cy_credits and e.cy_s1_ada < 0.9 and e.cy_s1_gpa >= 2.5
        then 'Probation - ADA'
        when e.met_cy_credits and e.cy_s1_ada < 0.9 and e.cy_s1_gpa between 2.2 and 2.49
        then 'Probation - ADA and GPA'
    end as q4_ae_status,
from students as e
inner join
    {{ ref("int_powerschool__gpprogress_grades") }} as g
    on e.studentsdcid = g.students_dcid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="g") }}
    and g.plan_name in ('NJ State Diploma', 'HS Distinction Diploma')
left join
    {{ ref("int_powerschool__gpprogress_grades") }} as sp
    on g.studentsdcid = sp.studentsdcid
    and g.plan_id = sp.id
    and {{ union_dataset_join_clause(left_alias="g", right_alias="sp") }}
    and sp.degree_plan_section = 'plan'
left join
    {{ ref("int_powerschool__gpprogress_grades") }} as sd
    on g.studentsdcid = sd.studentsdcid
    and g.discipline_id = sd.id
    and {{ union_dataset_join_clause(left_alias="g", right_alias="sd") }}
    and sd.degree_plan_section = 'discipline'
left join
    {{ ref("int_powerschool__gpprogress_grades") }} as ss
    on g.studentsdcid = ss.studentsdcid
    and g.subject_id = ss.id
    and {{ union_dataset_join_clause(left_alias="g", right_alias="ss") }}
    and ss.degree_plan_section = 'subject'
