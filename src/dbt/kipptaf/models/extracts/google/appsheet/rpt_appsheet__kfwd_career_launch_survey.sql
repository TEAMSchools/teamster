with
    survey_reconciliation_raw as (
        select response_id, item_title, text_value, create_timestamp,
        from {{ ref("int_google_forms__form_responses") }}
        where
            form_id = '1oUBls4Kaj0zcbQyeWowe8Es1BFqunolAPEamzT6enQs'
            and item_title in ('Survey response ID', 'Salesforce contact ID')
    ),

    survey_reconciliation as (
        select
            survey_response_id,
            sf_contact_id,

            row_number() over (
                partition by survey_response_id order by create_timestamp desc
            ) as rn_response_id,
        from
            survey_reconciliation_raw pivot (
                max(text_value) for item_title in (
                    'Survey response ID' as survey_response_id,
                    'Salesforce contact ID' as sf_contact_id
                )
            )
    ),

    current_enrollment as (
        select student, pursuing_degree_type, major,
        from {{ ref("stg_kippadb__enrollment") }}
        where type not in ('High School', 'Middle School')
        qualify
            row_number() over (partition by student order by start_date desc) = 1
    ),

    survey_union as (
        select
            ri.response_date_submitted,
            cast(ri.response_id as string) as response_id,
            lower(ri.respondent_user_principal_name) as respondent_user_principal_name,
        from {{ source("surveys", "int_surveys__response_identifiers") }} as ri
        where ri.survey_id = 6734664  /* 'KIPP Forward Career Launch Survey' */

        union all

        select
            safe_cast(fr.last_submitted_time as timestamp) as response_date_submitted,
            cast(fr.response_id as string) as response_id,
            lower(fr.respondent_email) as respondent_user_principal_name,
        from {{ ref("int_google_forms__form_responses") }} as fr
        /* 'KIPP Forward Career Launch Survey - OLD' */
        where fr.form_id = '1qfXBcMxp9712NEnqOZS2S-Zm_SAvXRi_UndXxYZUZho'

        union all

        select
            safe_cast(fr.last_submitted_time as timestamp) as response_date_submitted,
            cast(fr.response_id as string) as response_id,
            lower(fr.respondent_email) as respondent_user_principal_name,
        from {{ ref("int_google_forms__form_responses") }} as fr
        /* 'KIPP Forward Career Launch Survey' */
        where fr.form_id = '1c4SLP61YIVnUUvRl_IUdFuLXdtI1Vsq9OE3Jrz3HR0U'
    ),

    roster as (
        select
            r.contact_id,
            r.contact_first_name as first_name,
            r.contact_last_name as last_name,
            r.ktc_cohort,
            lower(r.contact_email) as sf_email,
            lower(r.contact_secondary_email) as sf_secondary_email,
            r.contact_currently_enrolled_school as currently_enrolled_school,
            r.contact_current_college_cumulative_gpa as current_college_cumulative_gpa,
            r.contact_mobile_phone as primary_phone,
            r.contact_home_phone as secondary_phone,
            r.contact_advising_provider as advising_provider,
            r.contact_expected_college_graduation as expected_college_grad_date,

            sr.survey_response_id as reconciliation_response_id,
        from {{ ref("int_kippadb__roster") }} as r
        left join
            survey_reconciliation as sr
            on r.contact_id = sr.sf_contact_id
            and sr.rn_response_id = 1
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
    coalesce(ss.survey_response_count, 0) as survey_response_count,
    ss.latest_survey_date,
from roster as r
left join current_enrollment as ce on r.contact_id = ce.student
left join survey_stats as ss on r.contact_id = ss.contact_id
