{{ config(enabled=False) }}
with
    transition as (
        select
            ktc.id as `Salesforce ID`,
            ktc.school_specific_id_c as `SIS ID`,
            ktc.first_name as `First Name`,
            ktc.last_name as `Last Name`,
            ktc.currently_enrolled_school_c as `Current Enrolled High School`,
            ktc.mobile_phone as `Student Cell Phone`,
            ktc.df_has_fafsa_c as `FAFSA Complete`,
            ktc.efc_from_fafsa_c as `EFC Actual`,
            ktc.expected_hs_graduation_c,
            ktc.college_match_display_gpa,
            ktc.highest_act_score,
            ktc.name as `College Counselor`,
            ktc.ps_contact_1_phone_primary as `Primary Phone`,
            ktc.ps_c_504_status as `504 Plan`,
            if(ktc.most_recent_iep_date_c is not null, 1, null) as `IEP`,
            if(
                ktc.latest_state_financial_aid_app_date_c is not null, 'Yes', 'No'
            ) as `HESAA Complete`,
            if(ktc.college_match_display_gpa >= 3.0, 1, 0) as gpa_higher_than_3,
            if(
                ktc.college_match_display_gpa between 2.5 and 2.9, 1, 0
            ) as gpa_between_25_29,
            if(
                ktc.ktc_status like 'TAF%',
                ktc.mailing_street
                || ' '
                || ktc.mailing_city
                || ', '
                || ktc.mailing_state
                || ' '
                || ktc.mailing_postal_code,
                ktc.ps_street
                || ' '
                || ktc.ps_city
                || ', '
                || ktc.ps_state
                || ' '
                || ktc.ps_zip
            ) as `Mailing Address`,
            if(
                ktc.ps_enroll_status = 0,
                coalesce(ktc.email, ktc.ps_student_web_id || '@teamstudents.org'),
                ktc.email
            ) as `Personal Email Address`,
            if(
                ktc.ktc_status like 'TAF%', null, ktc.ps_contact_1_name
            ) as `Primary Parent Name`,
            if(
                ktc.ktc_status like 'TAF%',
                ktc.sf_home_phone,
                ktc.ps_contact_1_phone_mobile
            ) as `Primary Parent Cell Phone`,
            if(
                ktc.ktc_status like 'TAF%',
                ktc.secondary_email_c,
                ktc.ps_contact_1_email_current
            ) as `Primary Parent Email`,

            if(cn.subject_c is null, 'No', 'Yes') as 'CCDM Complete',

            row_number() over (partition by ktc.id order by cn.date_c desc) as rn_ccdm
        from alumni.ktc_roster as kt
        left join
            alumni.contact_note_c as cn
            on ktc.sf_contact_id = cn.contact_c
            and cn.subject_c = 'CCDM'
            and cn.is_deleted = 0
        where ktc.is_deleted = 0
    )

select
    t.`Salesforce ID`,
    t.`SIS ID`,
    t.`College Counselor`,
    t.`First Name`,
    t.`Last Name`,
    t.`Current Enrolled High School`,
    t.`Student Cell Phone`,
    t.`Personal Email Address`,
    t.`Primary Parent Name`,
    t.`Primary Parent Cell Phone`,
    t.`Primary Parent Email`,
    t.`Mailing Address`,
    t.`IEP`,
    t.`504 Plan`,
    t.`FAFSA Complete`,
    t.`HESAA Complete`,
    t.`EFC Actual`,
    t.expected_hs_grad_date,
    t.college_match_display_gpa,
    t.highest_act_score,

    ap.application_id,
    ap.application_name,
    ap.matriculation_decision,

    t.`CCDM Complete`,
    t.gpa_higher_than_3,

    if(ac.x_6_yr_minority_completion_rate_c < 50, 1, 0) as minor_grad_rate_under50,

    t.gpa_between_25_29,

    if(ac.x_6_yr_minority_completion_rate_c < 40, 1, 0) as minor_grad_rate_under40,

    if(
        ktc.college_match_display_gpa >= 3.0
        and ac.x_6_yr_minority_completion_rate_c < 50,
        1,
        0
    ) as undermatch_3gpa,
    if(
        ktc.college_match_display_gpa between 2.5 and 2.9
        and ac.x_6_yr_minority_completion_rate_c < 40,
        1,
        0
    ) as undermatch_25_29gpa,
from transition as t
left join
    alumni.application_identifiers as ap
    on ktc.sf_contact_id = ap.sf_contact_id
    and ap.matriculation_decision = 'Matriculated (Intent to Enroll)'
left join alumni.enrollment_identifiers as ei on ei.student_c = ktc.sf_contact_id
left join alumni.account as ac on ac.ncesid_c = ei.ugrad_ncesid
where t.rn_ccdm = 1
