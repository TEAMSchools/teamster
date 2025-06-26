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
            u.degree_plan_section,
            u.node_id,
            u.node_name,
            u.node_credit_capacity,

            ps.requiredcredits,
            ps.enrolledcredits,
            ps.requestedcredits,
            ps.earnedcredits,
            ps.waivedcredits,
            ps.ccdcid,
            ps.storedgradesdcid,

        from gpn_unpivot as u
        left join
            {{ ref("int_powerschool__gpprogresssubject") }} as ps
            on u.node_id = ps.gpnodeid
            and {{ union_dataset_join_clause(left_alias="u", right_alias="ps") }}
    ),

    gps_grades as (
        select
            gp._dbt_source_relation,
            gp.root_node_id,
            gp.degree_plan_section,
            gp.node_id,
            gp.node_name,
            gp.node_credit_capacity,
            gp.requiredcredits,
            gp.enrolledcredits,
            gp.requestedcredits,
            gp.earnedcredits,
            gp.waivedcredits,

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

        from gpn_gps as gp
        inner join
            {{ ref("stg_powerschool__storedgrades") }} as sg
            on gp.storedgradesdcid = sg.dcid
            and {{ union_dataset_join_clause(left_alias="gp", right_alias="sg") }}
            and sg.storecode = 'Y1'

        union all

        select
            gp._dbt_source_relation,
            gp.root_node_id,
            gp.degree_plan_section,
            gp.node_id,
            gp.node_name,
            gp.node_credit_capacity,
            gp.requiredcredits,
            gp.enrolledcredits,
            gp.requestedcredits,
            gp.earnedcredits,
            gp.waivedcredits,

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

        from gpn_gps as gp
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

    ae.q1_ae_status,
    ae.q2_ae_status,
    ae.q3_ae_status,
    ae.q4_ae_status,

    gw.plan_id,
    gw.plan_name,
    gw.discipline_id,
    gw.discipline_name,
    gw.subject_id,
    gw.subject_name,

    gg.teacher_name,
    gg.course_number,
    gg.course_name,
    gg.sectionid,
    gg.credit_type,
    gg.letter_grade,
    gg.is_transfer_grade,
    gg.credit_status,
    gg.earned_credits,
    gg.potential_credits,

    up.requiredcredits as plan_required_credits,
    up.enrolledcredits as plan_enrolled_credits,
    up.requestedcredits as plan_requested_credits,
    up.earnedcredits as plan_earned_credits,
    up.waivedcredits as plan_waived_credits,

    ud.requiredcredits as discipline_required_credits,
    ud.enrolledcredits as discipline_enrolled_credits,
    ud.requestedcredits as discipline_requested_credits,
    ud.earnedcredits as discipline_earned_credits,
    ud.waivedcredits as discipline_waived_credits,

    us.requiredcredits as subject_required_credits,
    us.enrolledcredits as subject_enrolled_credits,
    us.requestedcredits as subject_requested_credits,
    us.earnedcredits as subject_earned_credits,
    us.waivedcredits as subject_waived_credits,

from {{ ref("int_extracts__student_enrollments") }} as e
left join
    {{ ref("int_students__athletic_eligibility") }} as ae
    on e.studentid = ae.studentid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="ae") }}
inner join
    {{ ref("int_powerschool__gpnode_wide") }} as gw
    on e._dbt_source_relation = gw._dbt_source_relation
    and {{ union_dataset_join_clause(left_alias="e", right_alias="gw") }}
    and gw.plan_name in ('NJ State Diploma', 'HS Distinction Diploma')
inner join
    gps_grades as gg
    on gw._dbt_source_relation = gg._dbt_source_relation
    and gw.plan_id = gg.root_node_id
    and {{ union_dataset_join_clause(left_alias="gw", right_alias="gg") }}
where
    e.academic_year = {{ var("current_academic_year") }}
    and e.enroll_status = 0
    and e.grade_level >= 9
