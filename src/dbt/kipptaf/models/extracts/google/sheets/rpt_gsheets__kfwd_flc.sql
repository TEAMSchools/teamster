with
    act_valid as (
        select
            school_specific_id as student_number,
            contact as contact_id,

            count(score_type) as act_count,
        from {{ ref("int_kippadb__standardized_test_unpivot") }}
        where score_type = 'act_composite'
        group by school_specific_id, contact
    ),

    early as (
        select applicant, max(is_early_action_decision) as is_ea_ed,
        from {{ ref("base_kippadb__application") }}
        group by applicant
    ),

    matriculated_application as (
        select
            applicant,
            adjusted_6_year_minority_graduation_rate as matriculated_ecc,
            intended_degree_type,
            account_type,
            matriculation_decision,

            row_number() over (partition by applicant order by id asc) as rn_applicant,
        from {{ ref("base_kippadb__application") }}
        where matriculation_decision = 'Matriculated (Intent to Enroll)'
    ),
with
    dps_responses as (
        select
            respondent_email, item_abbreviation, text_value, last_submitted_date_local,
        from {{ ref("base_google") }}
        where form_id = '1KD8HAfJNdaGNg2VJbxnJ5Wedf8wrPp1QnBYBEG2Elu4'
    ),
    dps_pivot as (
        select
            respondent_email,
            last_submitted_date_local as dps_submit_date_most_recent,
            desired_pathway as dps_desired_pathway,
            secondary_pathway as dps_secondary_pathway,
            interested_career_industry as dps_interested_career_industry,
            additional_future_plans as dps_additional_future_plans,
            kfwd_support as dps_kfwd_support,
            dream_career as dps_dream_career,
            row_number() over (
                partition by respondent_email order by last_submitted_date_local desc
            ) as rn_response,
        from
            dps_responses pivot (
                max(text_value) for item_abbreviation in (
                    'desired_pathway',
                    'secondary_pathway',
                    'interested_career_industry',
                    'additional_future_plans',
                    'kfwd_support',
                    'dream_career'
                )
            )
    )

-- trunk-ignore(sqlfluff/ST06)
select
    co.student_number,
    co.lastfirst as student_name,
    co.school_abbreviation as school,
    co.region,
    co.advisor_lastfirst as advisor,
    co.gender,
    co.student_email_google,

    ce.teacher_lastfirst as ccr_teacher,
    ce.sections_external_expression as ccr_period,

    kt.contact_owner_name as counselor_name,
    kt.contact_college_match_display_gpa,
    kt.contact_highest_act_score,
    kt.best_guess_pathway,

    coalesce(kt.contact_id, 'not in salesforce') as sf_id,

    if(co.spedlep like 'SPED%', 'Has IEP', 'No IEP') as iep_status,

    case
        when co.enroll_status = 0
        then 'currently enrolled'
        when co.enroll_status = 2
        then 'transferred out'
        when co.enroll_status = 3
        then 'graduated'
    end as enroll_status,

    concat(co.lastfirst, ' - ', co.student_number) as student_identifier,

    act.act_count,

    co.lep_status,

    case
        when kt.contact_college_match_display_gpa >= 3.50
        then '3.50+'
        when kt.contact_college_match_display_gpa >= 3.00
        then '3.00-3.49'
        when kt.contact_college_match_display_gpa >= 2.50
        then '2.50-2.99'
        when kt.contact_college_match_display_gpa >= 2.00
        then '2.00-2.50'
        when kt.contact_college_match_display_gpa < 2.00
        then '<2.00'
    end as hs_gpa_bands,

    coalesce(e.is_ea_ed, false) as is_ea_ed,

    m.matriculated_ecc,
    m.matriculation_decision,
    m.intended_degree_type,
    m.account_type,

    co.grade_level,

    kt.contact_expected_hs_graduation,

    coalesce(cn.ccdm, 0) as ccdm_complete,

    kt.ktc_status,

    if(
        kt.ktc_status not like 'TAF%' and co.enroll_status = 0,
        'KIPP Enrolled',
        kt.ktc_status
    ) as taf_enroll_status,

    gpa.cumulative_y1_gpa_unweighted,
    case
        when kt.contact_college_match_display_gpa >= 3.00
        then 'FLC Eligible'
        else 'Below FLC GPA'
    end as flc_eligibility,

    if(kt.overgrad_students_id is not null, 'Yes', 'No') as has_overgrad_account_yn,
    kt.overgrad_students_assigned_counselor_lastfirst as overgrad_counselor,

    dps.dps_submit_date_most_recent,
    dps.dps_desired_pathway,
    dps.dps_secondary_pathway,
    dps.dps_interested_career_industry,
    dps.dps_additional_future_plans,
    dps.dps_kfwd_support,
    dps.dps_dream_career,
from {{ ref("base_powerschool__student_enrollments") }} as co
left join
    {{ ref("int_kippadb__roster") }} as kt on co.student_number = kt.student_number
left join
    {{ ref("base_powerschool__course_enrollments") }} as ce
    on co.student_number = ce.students_student_number
    and co.academic_year = ce.cc_academic_year
    and ce.courses_course_name like 'College and Career%'
    and ce.rn_course_number_year = 1
    and not ce.is_dropped_section
left join act_valid as act on kt.contact_id = act.contact_id
left join early as e on kt.contact_id = e.applicant
left join
    matriculated_application as m on kt.contact_id = m.applicant and m.rn_applicant = 1
left join
    {{ ref("int_kippadb__contact_note_rollup") }} as cn
    on kt.contact_id = cn.contact_id
    and cn.academic_year = {{ var("current_academic_year") }}
left join
    {{ ref("int_powerschool__gpa_cumulative") }} as gpa
    on co.studentid = gpa.studentid
    and co.schoolid = gpa.schoolid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="gpa") }}
left join
    dps_pivot as dps
    on dps.dps_respondent_email = co.student_email_google
    and dps.rn_response = 1
where co.rn_undergrad = 1 and co.grade_level != 99
