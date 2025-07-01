with
    gpn_unpivot as (
        select
            _dbt_source_relation,
            root_node_id,

            /* unpivot columns */
            degree_plan_section,
            node_id,
            node_name,
            node_credit_capacity,

        from
            {{ ref("int_powerschool__gpnode_wide") }} unpivot (
                (node_id, node_name, node_credit_capacity) for degree_plan_section in (
                    (plan_id, plan_name, plan_credit_capacity) as 'plan',
                    (
                        discipline_id, discipline_name, discipline_credit_capacity
                    ) as 'discipline',
                    (subject_id, subject_name, subject_credit_capacity) as 'subject'
                )
            )
        where root_node_name in ('NJ State Diploma', 'HS Distinction Diploma')
    ),

    gpn_gps as (
        select
            u._dbt_source_relation,
            u.root_node_id,
            u.node_id,
            u.degree_plan_section,

            ps.studentsdcid,
            ps.enrolledcredits,
            ps.requestedcredits,
            ps.earnedcredits,
            ps.waivedcredits,
            ps.grade_dcid,
            ps.credit_status,

            coalesce(ps.requiredcredits, u.node_credit_capacity) as requiredcredits,

        from gpn_unpivot as u
        left join
            {{ ref("int_powerschool__gpprogresssubject") }} as ps
            on u.node_id = ps.gpnodeid
            and {{ union_dataset_join_clause(left_alias="u", right_alias="ps") }}
    ),

    gpn_gps_prepivot as (
        select
            _dbt_source_relation,
            root_node_id,
            studentsdcid,
            degree_plan_section,
            enrolledcredits,
            requestedcredits,
            earnedcredits,
            waivedcredits,
            requiredcredits,
        from gpn_gps
    ),

    gpn_gps_pivot as (
        select
            _dbt_source_relation,
            root_node_id,
            studentsdcid,

            /* pivot cols */
            earned_credits_discipline,
            earned_credits_plan,
            earned_credits_subject,
            enrolled_credits_discipline,
            enrolled_credits_plan,
            enrolled_credits_subject,
            requested_credits_discipline,
            requested_credits_plan,
            requested_credits_subject,
            required_credits_discipline,
            required_credits_plan,
            required_credits_subject,
            waived_credits_discipline,
            waived_credits_plan,
            waived_credits_subject,
        from
            gpn_gps_prepivot pivot (
                max(enrolledcredits) as enrolled_credits,
                max(requestedcredits) as requested_credits,
                max(earnedcredits) as earned_credits,
                max(waivedcredits) as waived_credits,
                max(requiredcredits) as required_credits
                for degree_plan_section in ('plan', 'discipline', 'subject')
            )
    ),

    gps_grades as (
        select
            gp._dbt_source_relation,
            gp.node_id,
            gp.credit_status,

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

        from gpn_gps as gp
        inner join
            {{ ref("stg_powerschool__storedgrades") }} as sg
            on gp.grade_dcid = sg.dcid
            and {{ union_dataset_join_clause(left_alias="gp", right_alias="sg") }}
            and sg.storecode = 'Y1'
        where gp.credit_status = 'Earned'

        union all

        select
            gp._dbt_source_relation,
            gp.node_id,
            gp.credit_status,

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

        from gpn_gps as gp
        inner join
            {{ ref("base_powerschool__final_grades") }} as fg
            on gp.grade_dcid = fg.cc_dcid
            and {{ union_dataset_join_clause(left_alias="gp", right_alias="fg") }}
            and fg.termbin_is_current
        where gp.credit_status = 'Enrolled'
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

    gw.plan_id,
    gw.plan_name,
    gw.discipline_id,
    gw.discipline_name,

    ggp.required_credits_plan as plan_required_credits,
    ggp.enrolled_credits_plan as plan_enrolled_credits,
    ggp.requested_credits_plan as plan_requested_credits,
    ggp.earned_credits_plan as plan_earned_credits,
    ggp.waived_credits_plan as plan_waived_credits,
    ggp.required_credits_discipline as discipline_required_credits,
    ggp.enrolled_credits_discipline as discipline_enrolled_credits,
    ggp.requested_credits_discipline as discipline_requested_credits,
    ggp.earned_credits_discipline as discipline_earned_credits,
    ggp.waived_credits_discipline as discipline_waived_credits,
    ggp.required_credits_subject as subject_required_credits,
    ggp.enrolled_credits_subject as subject_enrolled_credits,
    ggp.requested_credits_subject as subject_requested_credits,
    ggp.earned_credits_subject as subject_earned_credits,
    ggp.waived_credits_subject as subject_waived_credits,

    coalesce(gw.subject_id, gw.discipline_id) as subject_id,
    coalesce(gw.subject_name, gw.discipline_name) as subject_name,

    coalesce(ggs.teacher_name, ggd.teacher_name) as teacher_name,
    coalesce(ggs.course_number, ggd.course_number) as course_number,
    coalesce(ggs.course_name, ggd.course_name) as course_name,
    coalesce(ggs.sectionid, ggd.sectionid) as sectionid,
    coalesce(ggs.credit_type, ggd.credit_type) as credit_type,
    coalesce(ggs.letter_grade, ggd.letter_grade) as letter_grade,
    coalesce(ggs.is_transfer_grade, ggd.is_transfer_grade) as is_transfer_grade,
    coalesce(ggs.credit_status, ggd.credit_status) as credit_status,
    coalesce(ggs.earned_credits, ggd.earned_credits) as earned_credits,
    coalesce(ggs.potential_credits, ggd.potential_credits) as potential_credits,

from {{ ref("int_extracts__student_enrollments") }} as e
inner join
    {{ ref("int_powerschool__gpnode_wide") }} as gw
    on {{ union_dataset_join_clause(left_alias="e", right_alias="gw") }}
    and gw.plan_name in ('NJ State Diploma', 'HS Distinction Diploma')
inner join
    gpn_gps_pivot as ggp
    on gw.root_node_id = ggp.root_node_id
    and {{ union_dataset_join_clause(left_alias="gw", right_alias="ggp") }}
    and e.students_dcid = ggp.studentsdcid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="ggp") }}
left join
    gps_grades as ggd
    on e.studentid = ggd.studentid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="ggd") }}
    and gw.discipline_id = ggd.node_id
    and {{ union_dataset_join_clause(left_alias="gw", right_alias="ggd") }}
left join
    gps_grades as ggs
    on e.studentid = ggs.studentid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="ggs") }}
    and gw.subject_id = ggs.node_id
    and {{ union_dataset_join_clause(left_alias="gw", right_alias="ggs") }}
where
    e.academic_year = {{ var("current_academic_year") }}
    and e.enroll_status = 0
    and e.grade_level >= 9
