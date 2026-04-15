with
    google_forms_surveys as (
        -- TODO: upstream at response grain, no definition model (#3635)
        select distinct
            form_id as survey_id, info_title as survey_name, 'Google Forms' as platform,
        from {{ ref("int_google_forms__form_responses") }}
        where form_id is not null
    ),

    alchemer_surveys as (
        -- TODO: upstream at response grain, no definition model (#3635)
        select distinct
            safe_cast(survey_id as string) as survey_id,
            survey_title as survey_name,

            'Alchemer' as platform,
        from {{ source("alchemer", "base_alchemer__survey_results") }}
        where survey_id is not null
    ),

    archive_manager as (
        select
            'historic_alchemer_Manager_survey' as survey_id,
            'Manager Survey' as survey_name,

            'Alchemer' as platform,
    ),

    archive_support as (
        select
            'historic_alchemer_cmo_support_survey' as survey_id,
            'CMO & Support Survey History' as survey_name,

            'Alchemer' as platform,
    ),

    powerschool_family as (
        select
            'PowerSchool' as survey_id,
            'PowerSchool Family School Community Diagnostic' as survey_name,

            'PowerSchool' as platform,
    ),

    all_surveys as (
        select *,
        from google_forms_surveys
        union all
        select *,
        from alchemer_surveys
        union all
        select *,
        from archive_manager
        union all
        select *,
        from archive_support
        union all
        select *,
        from powerschool_family
    ),

    survey_classification as (
        select survey_name, survey_type, subject_area,
        from
            unnest(
                [
                    struct(
                        'School Community Diagnostic Staff Survey' as survey_name,
                        'School Community Diagnostic' as survey_type,
                        'School Culture' as subject_area
                    ),
                    struct(
                        'School Community Diagnostic Student Survey',
                        'School Community Diagnostic',
                        'School Culture'
                    ),
                    struct(
                        'KIPP NJ & KIPP Miami Family Survey',
                        'School Community Diagnostic',
                        'School Culture'
                    ),
                    struct(
                        'KIPP Miami Re-Commitment Form'
                        ' & Family School Community Diagnostic',
                        'School Community Diagnostic',
                        'School Culture'
                    ),
                    struct(
                        'PowerSchool Family School Community Diagnostic',
                        'School Community Diagnostic',
                        'School Culture'
                    ),
                    struct('Manager Survey', 'Manager Survey', 'Staff Experience'),
                    struct('Support Survey', 'Support Survey', 'Staff Experience'),
                    struct(
                        'CMO & Support Survey History',
                        'Support Survey',
                        'Staff Experience'
                    ),
                    struct('KTAF Support Survey', 'Support Survey', 'Staff Experience'),
                    struct(
                        'Engagement & Support Surveys',
                        'Engagement Survey',
                        'Staff Experience'
                    ),
                    struct('Self and Others', 'Climate Survey', cast(null as string)),
                    struct('TNTP Insight', 'Climate Survey', cast(null as string)),
                    struct(
                        'TNTP Insight Survey', 'Climate Survey', cast(null as string)
                    ),
                    struct('Gallup Q12 Survey', 'Climate Survey', cast(null as string)),
                    struct(
                        'Intent to Return Survey', 'Intent to Return', 'Staff Retention'
                    ),
                    struct(
                        'Staff Info & Certification Update',
                        'Staff Information',
                        'Staff Demographics'
                    ),
                    struct(
                        'Renewal Approval Tool Processing', 'Renewal', 'Staff Retention'
                    ),
                    struct(
                        'KIPP Forward Career Launch Survey',
                        'Career Launch',
                        'College & Career'
                    ),
                    struct(
                        'Career Launch Survey invalid response'
                        ' reconciliation',
                        'Career Launch',
                        'College & Career'
                    )
                ]
            )
    )

select
    {{ dbt_utils.generate_surrogate_key(["s.survey_id"]) }} as survey_key,

    s.survey_id,
    s.survey_name,

    coalesce(c.survey_type, 'Other') as survey_type,
    c.subject_area,
    s.platform,
from all_surveys as s
left join survey_classification as c on s.survey_name = c.survey_name
