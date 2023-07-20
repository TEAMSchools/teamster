{{ config(enabled=False) }}
with
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

            sum(is_submitted) as n_submitted,
            sum(is_accepted) as n_accepted,
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
        {#
            utilities.date_to_sy(transcript_date) as academic_year,
            case
                when month(transcript_date) = 1
                then 'fall'
                when month(transcript_date) = 5
                then 'spr'
            end as semester
        #}
        from {{ ref("stg_kippadb__gpa") }}
        where
            record_type_id
            in (select id from alumni.record_type where name = 'Cumulative College')
    ),

    semester_gpa_unpivot as (
        select student, academic_year, value, semester + '_' + field as pivot_field,
        from
            semester_gpa unpivot (
                value for field in (
                    transcript_date,
                    semester_gpa,
                    cumulative_gpa,
                    semester_credits_earned,
                    cumulative_credits_earned,
                    credits_required_for_graduation
                )
            ) as u
        where rn_semester = 1
    ),

    semester_gpa_pivot as (
        select
            sf_contact_id,
            academic_year,
            cast(fall_transcript_date as date) as fall_transcript_date,
            cast(
                fall_credits_required_for_graduation as float
            ) as fall_credits_required_for_graduation,
            cast(
                fall_cumulative_credits_earned as float
            ) as fall_cumulative_credits_earned,
            cast(fall_semester_credits_earned as float) as fall_semester_credits_earned,
            cast(fall_semester_gpa as float) as fall_semester_gpa,
            cast(fall_cumulative_gpa as float) as fall_cumulative_gpa,
            cast(spr_transcript_date as date) as spr_transcript_date,
            cast(
                spr_credits_required_for_graduation as float
            ) as spr_credits_required_for_graduation,
            cast(
                spr_cumulative_credits_earned as float
            ) as spr_cumulative_credits_earned,
            cast(spr_semester_credits_earned as float) as spr_semester_credits_earned,
            cast(spr_semester_gpa as float) as spr_semester_gpa,
            cast(spr_cumulative_gpa as float) as spr_cumulative_gpa
        from
            semster_gpa_unpivot pivot (
                max(value) for pivot_field in (
                    fall_credits_required_for_graduation,
                    fall_cumulative_credits_earned,
                    fall_cumulative_gpa,
                    fall_semester_credits_earned,
                    fall_semester_gpa,
                    fall_transcript_date,
                    spr_credits_required_for_graduation,
                    spr_cumulative_credits_earned,
                    spr_cumulative_gpa,
                    spr_semester_credits_earned,
                    spr_semester_gpa,
                    spr_transcript_date
                )
            )
    ),

    latest_note as (
        select
            contact,
            comments,
            next_steps,
            subject,
            utilities.date_to_sy(date) as academic_year,
            row_number() over (
                partition by contact, utilities.date_to_sy(date) order by date desc
            ) as rn
        from {{ ref("stg_kippadb__contact_note") }}
        where subject like 'AS[0-9]%'
    ),

    tier as (
        select
            contact,
            subject as tier,
            utilities.date_to_sy(date) as academic_year,
            row_number() over (
                partition by contact, utilities.date_to_sy(date) order by date desc
            ) as rn
        from {{ ref("stg_kippadb__contact_note") }}
        where subject like 'Tier [0-9]'
    ),

    matric as (
        select
            student as contact_id,
            id as enrollment_id,
            row_number() over (
                partition by student order by start_date desc
            ) as rn_matric
        from {{ ref("stg_kippadb__enrollment") }}
        where status = 'Matriculated'
    ),

    finaid as (
        select
            e.contact_id,
            fa.unmet_need,
            row_number() over (
                partition by e.enrollment_id order by fa.offer_date desc
            ) as rn_finaid
        from matric as e
        inner join
            {{ ref("stg_kippadb__subsequent_financial_aid_award") }} as fa
            on e.enrollment_id = fa.enrollment
            and fa.is_deleted = 0
            and fa.status = 'Offered'
        where e.rn_matric = 1
    ),

    grad_plan as (
        select
            kt.sf_contact_id,
            c.subject as grad_plan_year,
            row_number() over (partition by kt.sf_contact_id order by c.date desc) as rn
        from {{ ref("stg_kippadb__contact_note") }} as c
        left join
            {{ ref("int_kippadb__ktc_roster") }} as kt on kt.sf_contact_id = c.contact
        where c.subject like 'Grad Plan FY%'
    )

select
    c.sf_contact_id,
    c.lastfirst as student_name,
    c.ktc_cohort,
    c.is_kipp_ms_graduate,
    c.is_kipp_hs_graduate,
    c.expected_hs_graduation_date,
    c.actual_hs_graduation_date,
    c.expected_college_graduation_date,
    c.actual_college_graduation_date,
    c.current_kipp_student,
    c.highest_act_score,
    c.record_type_name,
    c.counselor_name,
    c.college_match_display_gpa,
    c.current_college_cumulative_gpa,
    c.kipp_region_name,
    c.post_hs_simple_admin,
    c.currently_enrolled_school,
    c.latest_fafsa_date,
    c.latest_state_financial_aid_app_date,
    c.most_recent_iep_date,
    c.latest_resume_date,
    c.efc_from_fafsa,
    c.ethnicity,
    c.gender,
    c.last_successful_contact_date,
    c.last_successful_advisor_contact_date,
    c.last_outreach_date,
    c.contact_description,
    c.high_school_graduated_from,
    c.college_graduated_from,
    c.current_college_semester_gpa,
    c.sf_email as email,
    c.sf_mobile_phone as mobile_phone,
    c.middle_school_attended,
    c.postsecondary_status,

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

    apps.application_name,
    apps.application_account_type,

    ar.n_submitted,
    ar.is_submitted_aa,
    ar.is_submitted_ba,
    ar.is_submitted_cert,
    ar.n_accepted,
    ar.is_accepted_aa,
    ar.is_accepted_ba,
    ar.is_accepted_cert,
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

    gpa.fall_transcript_date,
    gpa.fall_semester_gpa,
    gpa.fall_cumulative_gpa,
    gpa.fall_semester_credits_earned,
    gpa.spr_transcript_date,
    gpa.spr_semester_gpa,
    gpa.spr_cumulative_gpa,
    gpa.spr_semester_credits_earned,
    coalesce(
        gpa.fall_cumulative_credits_earned,
        /* prev spring */
        lag(gpa.spr_cumulative_credits_earned, 1) over (
            partition by c.sf_contact_id order by ay.academic_year asc
        ),
        /* prev fall */
        lag(gpa.fall_cumulative_credits_earned, 1) over (
            partition by c.sf_contact_id order by ay.academic_year asc
        )
    ) as fall_cumulative_credits_earned,
    coalesce(
        gpa.spr_cumulative_credits_earned,
        gpa.fall_cumulative_credits_earned,
        /* prev spring */
        lag(gpa.spr_cumulative_credits_earned, 1) over (
            partition by c.sf_contact_id order by ay.academic_year asc
        ),
        /* prev fall */
        lag(gpa.fall_cumulative_credits_earned, 1) over (
            partition by c.sf_contact_id order by ay.academic_year asc
        )
    ) as spr_cumulative_credits_earned,
    lag(gpa.spr_semester_credits_earned, 1) over (
        partition by c.sf_contact_id order by ay.academic_year asc
    ) as prev_spr_semester_credits_earned,

    ln.comments as latest_as_comments,
    ln.next_steps as latest_as_next_steps,

    fa.unmet_need as unmet_need,

    tier.tier,

    gp.grad_plan_year as most_recent_grad_plan_year,

    c.advising_provider,
from {{ ref("int_kippadb__ktc_roster") }} as c
cross join academic_years as ay
left join
    {{ ref("int_kippadb__enrollment_pivot") }} as ei on c.sf_contact_id = ei.student
left join
    {{ ref("base_kippadb__application") }}
    on c.contact_id = apps.applicant
    and apps.matriculation_decision = 'Matriculated (Intent to Enroll)'
    and apps.transfer_application = 0
    and apps.rn = 1
left join app_rollup as ar on c.sf_contact_id = ar.sf_contact_id
left join
    {{ ref("int_kippadb__contact_note_rollup") }} as cnr
    on c.sf_contact_id = cnr.contact_id
    and ay.academic_year = cnr.academic_year
left join
    semester_gpa_pivot as gpa
    on c.sf_contact_id = gpa.sf_contact_id
    and ay.academic_year = gpa.academic_year
left join
    latest_note as ln
    on c.sf_contact_id = ln.contact
    and ay.academic_year = ln.academic_year
    and ln.rn = 1
left join finaid as fa on c.sf_contact_id = fa.contact_id and fa.rn_finaid = 1
left join
    tier
    on c.sf_contact_id = tier.contact
    and ay.academic_year = tier.academic_year
    and tier.rn = 1
left join grad_plan as gp on c.sf_contact_id = gp.sf_contact_id and gp.rn = 1
where
    c.ktc_status in ('HS9', 'HS10', 'HS11', 'HS12', 'HSG', 'TAF', 'TAFHS')
    and c.sf_contact_id is not null
