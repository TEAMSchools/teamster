with
    current_enrollment as (
        select student, pursuing_degree_type, major,
        from {{ ref("stg_kippadb__enrollment") }}
        where type not in ('High School', 'Middle School')
        qualify row_number() over (partition by student order by start_date desc) = 1
    ),

    roster as (
        select
            r.contact_id,
            r.contact_first_name as first_name,
            r.contact_last_name as last_name,
            r.ktc_cohort,
            r.contact_currently_enrolled_school as currently_enrolled_school,
            r.contact_current_college_cumulative_gpa as current_college_cumulative_gpa,
            r.contact_mobile_phone as primary_phone,
            r.contact_home_phone as secondary_phone,
            r.contact_advising_provider as advising_provider,
            r.contact_expected_college_graduation as expected_college_grad_date,
            r.contact_owner_name as contact_owner,
            r.contact_postsec_advisor as postsec_advisor,
            r.contact_current_college_cumulative_gpa_source
            as current_college_cumulative_gpa_source,

            lower(r.contact_email) as sf_email,
            lower(r.contact_secondary_email) as sf_secondary_email,
        from {{ ref("int_kippadb__roster") }} as r
        where
            r.ktc_status in ('HSG', 'TAF')
            and r.contact_id is not null
            and r.ktc_cohort <= {{ var("current_academic_year") }}
    ),

    survey_responses as (
        select
            cr.response_id,
            cr.response_date_submitted,
            cr.respondent_user_principal_name,
            cr.respondent_salesforce_id,

            sr.sf_contact_id as reconciled_contact_id,
        from {{ ref("int_surveys__kfwd_career_launch_responses") }} as cr
        left join
            {{ ref("int_surveys__kfwd_career_launch_reconciliation") }} as sr
            on cr.response_id = sr.survey_response_id
        where sr.reconcile_or_exclude is distinct from 'Exclude'
    ),

    survey_stats as (
        select
            r.contact_id,

            count(distinct su.response_id) as survey_response_count,

            max(su.response_date_submitted) as latest_survey_date,
        from roster as r
        inner join
            survey_responses as su
            on r.sf_email = su.respondent_user_principal_name
            or r.sf_secondary_email = su.respondent_user_principal_name
            or r.contact_id = su.reconciled_contact_id
            or r.contact_id = su.respondent_salesforce_id
        group by r.contact_id
    )

select
    r.contact_id,
    r.first_name,
    r.last_name,
    r.ktc_cohort,
    r.sf_email as primary_email,
    r.sf_secondary_email as secondary_email,
    r.currently_enrolled_school,
    r.current_college_cumulative_gpa,
    r.primary_phone,
    r.secondary_phone,
    r.advising_provider,
    r.expected_college_grad_date,
    r.contact_owner,
    r.postsec_advisor,
    r.current_college_cumulative_gpa_source,

    ce.pursuing_degree_type,
    ce.major,

    ss.latest_survey_date,

    clc.gpa_band,
    clc.gpa_points,
    clc.ecc,

    coalesce(ss.survey_response_count, 0) as survey_response_count,

    if(r.advising_provider = 'KIPP NYC', 'Collab', r.contact_owner) as advisor,
from roster as r
left join current_enrollment as ce on r.contact_id = ce.student
left join survey_stats as ss on r.contact_id = ss.contact_id
left join
    {{ ref("int_surveys__kfwd_career_launch_contacts") }} as clc
    on r.contact_id = clc.contact_id
