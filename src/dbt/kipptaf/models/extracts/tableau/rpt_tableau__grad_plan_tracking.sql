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

            gty.gpa_y1,

            if(
                g.academic_year = {{ var("current_academic_year") }}, true, false
            ) as is_current_academic_year,

            if(
                g.academic_year = {{ var("current_academic_year") - 1 }}, true, false
            ) as is_previous_academic_year,

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
    ),

    yearly_credits as (
        select
            *,

            sum(earned_credits) over (
                partition by academic_year, student_number, plan_id
            ) as academic_year_credits_earned,

            sum(potential_credits) over (
                partition by academic_year, student_number, plan_id
            ) as academic_year_credits_potential,

        from credits
    ),

    custom_yearly_credits as (
        select
            _dbt_source_relation,
            student_number,
            plan_id,

            avg(
                case
                    when is_previous_academic_year then academic_year_credits_earned
                end
            ) as earned_credits_previous_year,

            avg(
                case when is_current_academic_year then academic_year_credits_earned end
            ) as earned_credits_current_year,

            avg(
                case
                    when is_current_academic_year
                    then (0.5 * academic_year_credits_earned)
                end
            ) as half_earned_credits_current_year,

            avg(
                case
                    when is_current_academic_year then academic_year_credits_potential
                end
            ) as potential_credits_current_year,

        from yearly_credits
        group by _dbt_source_relation, student_number, plan_id
    )

select
    y.*,

    c.earned_credits_previous_year,
    c.earned_credits_current_year,
    c.half_earned_credits_current_year,
    c.potential_credits_current_year,

    {{ var("current_academic_year") }} as current_academic_year,

    if(
        potential_credits_current_year / 2 = c.half_earned_credits_current_year,
        true,
        false
    ) as is_cy_credits_on_track,

from yearly_credits as y
inner join
    custom_yearly_credits as c
    on y.student_number = c.student_number
    and y.plan_id = c.plan_id
    and {{ union_dataset_join_clause(left_alias="y", right_alias="c") }}
where y.plan_name in ('NJ State Diploma', 'HS Distinction Diploma')
and y.enroll_status = 0
