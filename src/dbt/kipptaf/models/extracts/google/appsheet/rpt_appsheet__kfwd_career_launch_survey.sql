with
    survey_reconciliation as (
        select
            *,
        from {{ ref("int_surveys__kfwd_career_launch_reconciliation") }}
    ),

    current_enrollment as (
        select student, pursuing_degree_type, major,
        from {{ ref("stg_kippadb__enrollment") }}
        where type not in ('High School', 'Middle School')
        qualify row_number() over (partition by student order by start_date desc) = 1
    ),

    survey_union as (
        select
            *,
        from {{ ref("int_surveys__kfwd_career_launch_responses") }}
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
            sr.survey_response_id as reconciliation_response_id,
            lower(r.contact_email) as sf_email,
            lower(r.contact_secondary_email) as sf_secondary_email,
        from {{ ref("int_kippadb__roster") }} as r
        left join survey_reconciliation as sr on r.contact_id = sr.sf_contact_id
        where
            r.ktc_status in ('HSG', 'TAF')
            and r.ktc_cohort <= {{ var("current_academic_year") }}
            and r.contact_id is not null
    ),

    survey_stats as (
        select
            r.contact_id,
            count(distinct su.response_id) as survey_response_count,
            max(su.response_date_submitted) as latest_survey_date,
        from roster as r
        inner join
            survey_union as su
            on r.sf_email = su.respondent_user_principal_name
            or r.sf_secondary_email = su.respondent_user_principal_name
            or r.reconciliation_response_id = su.response_id
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
    ce.pursuing_degree_type,
    ce.major,
    r.primary_phone,
    r.secondary_phone,
    r.advising_provider,
    r.expected_college_grad_date,
    ss.latest_survey_date,
    coalesce(ss.survey_response_count, 0) as survey_response_count,
from roster as r
left join current_enrollment as ce on r.contact_id = ce.student
left join survey_stats as ss on r.contact_id = ss.contact_id
