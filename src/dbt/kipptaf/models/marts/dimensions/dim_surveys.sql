with
    google_forms_surveys as (
        -- TODO: upstream at response grain, no definition model (#3635)
        select distinct form_id as survey_id, info_title as survey_name,
        from {{ ref("int_google_forms__form_responses") }}
        where form_id is not null
    ),

    alchemer_surveys as (
        -- TODO: upstream at response grain, no definition model (#3635)
        select distinct
            safe_cast(survey_id as string) as survey_id, survey_title as survey_name,
        from {{ source("alchemer", "base_alchemer__survey_results") }}
        where survey_id is not null
    ),

    archive_manager as (
        select
            'historic_alchemer_Manager_survey' as survey_id,
            'Manager Survey' as survey_name,
    ),

    archive_support as (
        select
            'historic_alchemer_cmo_support_survey' as survey_id,
            'CMO & Support Survey History' as survey_name,
    ),

    powerschool_family as (
        select
            'PowerSchool' as survey_id,
            'PowerSchool Family School Community Diagnostic' as survey_name,
    ),

    all_surveys as (
        select *
        from google_forms_surveys
        union all
        select *
        from alchemer_surveys
        union all
        select *
        from archive_manager
        union all
        select *
        from archive_support
        union all
        select *
        from powerschool_family
    )

select
    {{ dbt_utils.generate_surrogate_key(["survey_id"]) }} as survey_key,

    survey_id,
    survey_name,

    case
        when
            survey_name in (
                'School Community Diagnostic Staff Survey',
                'School Community Diagnostic Student Survey',
                'KIPP NJ & KIPP Miami Family Survey',
                'KIPP Miami Re-Commitment Form'
                ' & Family School Community Diagnostic',
                'PowerSchool Family School Community Diagnostic'
            )
        then 'School Community Diagnostic'
        when survey_name in ('Manager Survey')
        then 'Manager Survey'
        when
            survey_name
            in ('Support Survey', 'CMO & Support Survey History', 'KTAF Support Survey')
        then 'Support Survey'
        when survey_name in ('Engagement & Support Surveys')
        then 'Engagement Survey'
        when
            survey_name in (
                'Self and Others',
                'TNTP Insight',
                'TNTP Insight Survey',
                'Gallup Q12 Survey'
            )
        then 'Climate Survey'
        when survey_name = 'Intent to Return Survey'
        then 'Intent to Return'
        when survey_name = 'Staff Info & Certification Update'
        then 'Staff Information'
        when survey_name = 'Renewal Approval Tool Processing'
        then 'Renewal'
        when
            survey_name in (
                'KIPP Forward Career Launch Survey',
                'Career Launch Survey invalid response'
                ' reconciliation'
            )
        then 'Career Launch'
        else 'Other'
    end as survey_type,

    case
        when
            survey_name in (
                'School Community Diagnostic Staff Survey',
                'School Community Diagnostic Student Survey',
                'KIPP NJ & KIPP Miami Family Survey',
                'KIPP Miami Re-Commitment Form'
                ' & Family School Community Diagnostic',
                'PowerSchool Family School Community Diagnostic'
            )
        then 'School Culture'
        when
            survey_name in (
                'Manager Survey',
                'Support Survey',
                'CMO & Support Survey History',
                'KTAF Support Survey',
                'Engagement & Support Surveys'
            )
        then 'Staff Experience'
        when survey_name = 'Intent to Return Survey'
        then 'Staff Retention'
        when survey_name = 'Staff Info & Certification Update'
        then 'Staff Demographics'
        when survey_name = 'Renewal Approval Tool Processing'
        then 'Staff Retention'
        when
            survey_name in (
                'KIPP Forward Career Launch Survey',
                'Career Launch Survey invalid response'
                ' reconciliation'
            )
        then 'College & Career'
        else null
    end as subject_area,

    case
        when survey_name like '%Alchemer%' or survey_name like '%historic_alchemer%'
        then 'Alchemer'
        when survey_name = 'PowerSchool Family School Community Diagnostic'
        then 'PowerSchool'
        else 'Google Forms'
    end as platform,
from all_surveys
