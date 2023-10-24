with
    year_scaffold as (
        select {{ var("current_academic_year") }} as academic_year
        union distinct
        select {{ var("current_academic_year") }} - 1 as academic_year
    ),

    app_rollup as (
        select
            applicant,
            max(is_eof) as is_eof_applicant,
            max(is_matriculated) as is_matriculated,
            max(is_submitted_aa) as is_submitted_aa,
            max(is_submitted_ba) as is_submitted_ba,
            max(is_submitted_certificate) as is_submitted_certificate,
            max(is_accepted_aa) as is_accepted_aa,
            max(is_accepted_ba) as is_accepted_ba,
            max(is_accepted_certificate) as is_accepted_certificate,

            sum(if(is_submitted, 1, 0)) as n_submitted,
            sum(if(is_accepted, 1, 0)) as n_accepted,
        from {{ ref("base_kippadb__application") }}
        group by applicant
    ),

    semester_gpa as (
        select
            student,
            transcript_date,
            semester_gpa,
            gpa as cumulative_gpa,
            semester_credits_earned,
            cumulative_credits_earned,
            credits_required_for_graduation,
            academic_year,
            semester,
            row_number() over (
                partition by student, academic_year, semester
                order by transcript_date desc
            ) as rn_semester,
        from {{ ref("stg_kippadb__gpa") }}
        where
            record_type_id in (
                select id
                from {{ ref("stg_kippadb__record_type") }}
                where name = 'Cumulative College'
            )
    ),

    latest_note as (
        select
            contact,
            academic_year,
            comments,
            next_steps,
            row_number() over (
                partition by contact, academic_year order by `date` desc
            ) as rn_contact_year_desc,
        from {{ ref("stg_kippadb__contact_note") }}
        where regexp_contains(`subject`, r'^AS\d')
    ),

    tier as (
        select
            contact,
            academic_year,
            `subject` as tier,
            row_number() over (
                partition by contact, academic_year order by `date` desc
            ) as rn_contact_year_desc,
        from {{ ref("stg_kippadb__contact_note") }}
        where regexp_contains(subject, r'Tier\s\d$')
    ),

    grad_plan as (
        select
            contact,
            `subject` as grad_plan_year,
            row_number() over (
                partition by contact order by `date` desc
            ) as rn_contact_desc,
        from {{ ref("stg_kippadb__contact_note") }}
        where `subject` like 'Grad Plan FY%'
    ),

    matric as (
        select
            id,
            student,

            row_number() over (
                partition by student order by `start_date` desc
            ) as rn_matric,
        from {{ ref("stg_kippadb__enrollment") }}
        where status = 'Matriculated'
    ),

    finaid as (
        select
            e.student,

            fa.unmet_need,

            row_number() over (
                partition by e.id order by fa.offer_date desc
            ) as rn_finaid,
        from matric as e
        inner join
            {{ ref("stg_kippadb__subsequent_financial_aid_award") }} as fa
            on e.id = fa.enrollment
            and fa.status = 'Offered'
        where e.rn_matric = 1
    ),

    benchmark as (
        select
            contact,
            academic_year,
            benchmark_date,
            benchmark_path,
            enrollment as benchmark_school_enrolled,
            date_completed as benchmark_completion_date,
            benchmark_status as benchmark_status,
            benchmark_period as benchmark_semester,
            overall_score as benchmark_overall_color,
            academic_color as benchmark_academic_color,
            financial_color as benchmark_financial_color,
            passion_purpose_plan_score as benchmark_ppp_color,
            row_number() over (
                partition by contact, academic_year order by benchmark_date desc
            ) as rn_benchmark,
        from {{ ref("stg_kippadb__college_persistence") }}
    )

select
    c.contact_id,
    c.lastfirst as student_name,
    c.ktc_cohort,
    c.record_type_name as record_type_name,
    c.contact_owner_name as counselor_name,
    c.contact_kipp_ms_graduate as is_kipp_ms_graduate,
    c.contact_kipp_hs_graduate as is_kipp_hs_graduate,
    c.contact_current_kipp_student as current_kipp_student,
    c.contact_highest_act_score as highest_act_score,
    c.contact_college_match_display_gpa as college_match_display_gpa,
    c.contact_current_college_cumulative_gpa as current_college_cumulative_gpa,
    c.contact_kipp_region_name as kipp_region_name,
    c.contact_dep_post_hs_simple_admin as post_hs_simple_admin,
    c.contact_currently_enrolled_school as currently_enrolled_school,
    c.contact_efc_from_fafsa as efc_from_fafsa,
    c.contact_ethnicity as ethnicity,
    c.contact_gender as gender,
    c.contact_description as contact_description,
    c.contact_high_school_graduated_from as high_school_graduated_from,
    c.contact_college_graduated_from as college_graduated_from,
    c.contact_current_college_semester_gpa as current_college_semester_gpa,
    c.contact_middle_school_attended as middle_school_attended,
    c.contact_postsecondary_status as postsecondary_status,
    c.contact_advising_provider as advising_provider,
    c.contact_email as email,
    c.contact_mobile_phone as mobile_phone,
    c.contact_expected_hs_graduation as expected_hs_graduation_date,
    c.contact_actual_hs_graduation_date as actual_hs_graduation_date,
    c.contact_actual_college_graduation_date as actual_college_graduation_date,
    c.contact_latest_fafsa_date as latest_fafsa_date,
    c.contact_most_recent_iep_date as most_recent_iep_date,
    c.contact_latest_state_financial_aid_app_date
    as latest_state_financial_aid_app_date,
    c.contact_expected_college_graduation as expected_college_graduation_date,
    c.contact_latest_resume as latest_resume_date,
    c.contact_last_successful_contact as last_successful_contact_date,
    c.contact_last_successful_advisor_contact as last_successful_advisor_contact_date,
    c.contact_last_outreach as last_outreach_date,

    ay.academic_year,

    ei.cur_school_name,
    ei.cur_account_type,
    ei.cur_pursuing_degree_type,
    ei.cur_status,
    ei.cur_start_date,
    ei.cur_actual_end_date,
    ei.cur_anticipated_graduation,
    ei.cur_credits_required_for_graduation,
    ei.cur_date_last_verified,
    ei.ecc_school_name,
    ei.ecc_account_type,
    ei.ecc_pursuing_degree_type,
    ei.ecc_status,
    ei.ecc_start_date,
    ei.ecc_actual_end_date,
    ei.ecc_anticipated_graduation,
    ei.ecc_credits_required_for_graduation,
    ei.ecc_date_last_verified,
    ei.emp_status,
    ei.emp_category,
    ei.emp_date_last_verified,
    ei.emp_start_date,
    ei.emp_actual_end_date,
    ei.emp_name,
    ei.ba_status,
    ei.ba_actual_end_date,
    ei.aa_status,
    ei.aa_actual_end_date,
    ei.cte_status,
    ei.cte_actual_end_date,
    ei.hs_account_name,
    ei.ugrad_adjusted_6_year_minority_graduation_rate,
    ei.ugrad_act_composite_25_75,
    ei.ugrad_competitiveness_ranking,

    apps.name as application_name,
    apps.account_type as application_account_type,

    ar.n_submitted,
    ar.is_submitted_aa,
    ar.is_submitted_ba,
    ar.is_submitted_certificate as is_submitted_cert,
    ar.n_accepted,
    ar.is_accepted_aa,
    ar.is_accepted_ba,
    ar.is_accepted_certificate as is_accepted_cert,
    ar.is_eof_applicant,
    ar.is_matriculated,

    cnr.as1,
    cnr.as2,
    cnr.as3,
    cnr.as4,
    cnr.as5,
    cnr.as6,
    cnr.as7,
    cnr.as8,
    cnr.as9,
    cnr.as10,
    cnr.as11,
    cnr.as12,
    cnr.as13,
    cnr.as14,
    cnr.as15,
    cnr.as16,
    cnr.as17,
    cnr.as18,
    cnr.as19,
    cnr.as20,
    cnr.as21,
    cnr.as22,
    cnr.as23,
    cnr.as24,
    cnr.as1_date,
    cnr.as2_date,
    cnr.as3_date,
    cnr.as4_date,
    cnr.as5_date,
    cnr.as6_date,
    cnr.as7_date,
    cnr.as8_date,
    cnr.as9_date,
    cnr.as10_date,
    cnr.as11_date,
    cnr.as12_date,
    cnr.as13_date,
    cnr.as14_date,
    cnr.as15_date,
    cnr.as16_date,
    cnr.as17_date,
    cnr.as18_date,
    cnr.as19_date,
    cnr.as20_date,
    cnr.as21_date,
    cnr.as22_date,
    cnr.as23_date,
    cnr.as24_date,
    cnr.ccdm,
    cnr.hd_p,
    cnr.hd_nr,
    cnr.td_p,
    cnr.td_nr,
    cnr.psc,
    cnr.sc,
    cnr.hv,
    cnr.dp_2year,
    cnr.dp_4year,
    cnr.dp_cte,
    cnr.dp_military,
    cnr.dp_workforce,
    cnr.dp_unknown,
    cnr.bgp_2year,
    cnr.bgp_4year,
    cnr.bgp_cte,
    cnr.bgp_military,
    cnr.bgp_workforce,
    cnr.bgp_unknown,

    gpa_fall.transcript_date as fall_transcript_date,
    gpa_fall.semester_gpa as fall_semester_gpa,
    gpa_fall.cumulative_gpa as fall_cumulative_gpa,
    gpa_fall.semester_credits_earned as fall_semester_credits_earned,

    gpa_spr.transcript_date as spr_transcript_date,
    gpa_spr.semester_gpa as spr_semester_gpa,
    gpa_spr.cumulative_gpa as spr_cumulative_gpa,
    gpa_spr.semester_credits_earned as spr_semester_credits_earned,
    lag(gpa_spr.semester_credits_earned, 1) over (
        partition by c.contact_id order by ay.academic_year asc
    ) as prev_spr_semester_credits_earned,

    coalesce(
        gpa_fall.cumulative_credits_earned,
        /* prev spring */
        lag(gpa_spr.cumulative_credits_earned, 1) over (
            partition by c.contact_id order by ay.academic_year asc
        ),
        /* prev fall */
        lag(gpa_fall.cumulative_credits_earned, 1) over (
            partition by c.contact_id order by ay.academic_year asc
        )
    ) as fall_cumulative_credits_earned,

    coalesce(
        gpa_spr.cumulative_credits_earned,
        gpa_fall.cumulative_credits_earned,
        /* prev spring */
        lag(gpa_spr.cumulative_credits_earned, 1) over (
            partition by c.contact_id order by ay.academic_year asc
        ),
        /* prev fall */
        lag(gpa_fall.cumulative_credits_earned, 1) over (
            partition by c.contact_id order by ay.academic_year asc
        )
    ) as spr_cumulative_credits_earned,

    ln.comments as latest_as_comments,
    ln.next_steps as latest_as_next_steps,

    tier.tier,

    gp.grad_plan_year as most_recent_grad_plan_year,

    fa.unmet_need as unmet_need,

    b.benchmark_school_enrolled,
    b.benchmark_path,
    b.benchmark_date,
    b.benchmark_status,
    b.benchmark_semester,
    b.benchmark_overall_color,
    b.benchmark_academic_color,
    b.benchmark_financial_color,
    b.benchmark_ppp_color,
from {{ ref("int_kippadb__roster") }} as c
cross join year_scaffold as ay
left join {{ ref("int_kippadb__enrollment_pivot") }} as ei on c.contact_id = ei.student
left join
    {{ ref("base_kippadb__application") }} as apps
    on c.contact_id = apps.applicant
    and apps.matriculation_decision = 'Matriculated (Intent to Enroll)'
    and not apps.transfer_application
    and apps.rn_app_enr = 1
left join app_rollup as ar on c.contact_id = ar.applicant
left join
    {{ ref("int_kippadb__contact_note_rollup") }} as cnr
    on c.contact_id = cnr.contact_id
    and ay.academic_year = cnr.academic_year
left join
    semester_gpa as gpa_fall
    on c.contact_id = gpa_fall.student
    and ay.academic_year = gpa_fall.academic_year
    and gpa_fall.semester = 'Fall'
    and gpa_fall.rn_semester = 1
left join
    semester_gpa as gpa_spr
    on c.contact_id = gpa_spr.student
    and ay.academic_year = gpa_spr.academic_year
    and gpa_spr.semester = 'Spring'
    and gpa_spr.rn_semester = 1
left join
    latest_note as ln
    on c.contact_id = ln.contact
    and ay.academic_year = ln.academic_year
    and ln.rn_contact_year_desc = 1
left join
    tier
    on c.contact_id = tier.contact
    and ay.academic_year = tier.academic_year
    and tier.rn_contact_year_desc = 1
left join grad_plan as gp on c.contact_id = gp.contact and gp.rn_contact_desc = 1
left join finaid as fa on c.contact_id = fa.student and fa.rn_finaid = 1
left join
    benchmark as b
    on c.contact_id = b.contact
    and ay.academic_year = b.academic_year
    and b.rn_benchmark = 1
where
    c.ktc_status in ('HS9', 'HS10', 'HS11', 'HS12', 'HSG', 'TAF', 'TAFHS')
    and c.contact_id is not null
