with
    credits as (
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
            g.credits,

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

            gty.gpa_y1,

            if(
                g.academic_year = {{ var("current_academic_year") }}, true, false
            ) as current_academic_year,

            if(
                g.academic_year = {{ var("current_academic_year") - 1 }}, true, false
            ) as previous_academic_year,

            case
                when
                    g.credit_status = 'Enrolled'
                    and g.credits is not null
                    and g.credits != ss.enrolledcredits
                then ss.enrolledcredits
                else g.credits
            end as credits_adjusted,

        from {{ ref("int_powerschool__gpprogress_grades") }} as g
        left join
            {{ ref("int_extracts__student_enrollments") }} as e
            on g.studentsdcid = e.students_dcid
            and {{ union_dataset_join_clause(left_alias="g", right_alias="e") }}
            and e.academic_year = {{ var("current_academic_year") }}
        left join
            {{ ref("int_powerschool__gpprogresssubject") }} as sp
            on g.studentsdcid = sp.studentsdcid
            and g.plan_id = sp.id
            and {{ union_dataset_join_clause(left_alias="g", right_alias="sp") }}
            and sp.degree_plan_section = 'Plan'
        left join
            {{ ref("int_powerschool__gpprogresssubject") }} as sd
            on g.studentsdcid = sd.studentsdcid
            and g.discipline_id = sd.id
            and {{ union_dataset_join_clause(left_alias="g", right_alias="sd") }}
            and sd.degree_plan_section = 'Discipline'
        left join
            {{ ref("int_powerschool__gpprogresssubject") }} as ss
            on g.studentsdcid = ss.studentsdcid
            and g.subject_id = ss.id
            and {{ union_dataset_join_clause(left_alias="g", right_alias="ss") }}
            and ss.degree_plan_section = 'Subject'
        left join
            {{ ref("int_powerschool__gpa_term") }} as gty
            on e.studentid = gty.studentid
            and e.yearid = gty.yearid
            and e.schoolid = gty.schoolid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="gty") }}
            and gty.is_current
    )

select
    *,

    (credits_adjusted / 2) as credits_adjusted_half,

    sum(credits_adjusted) over (
        partition by _dbt_source_relation, academic_year, plan_id, studentsdcid
    ) as academic_year_credits_earned,

from credits
