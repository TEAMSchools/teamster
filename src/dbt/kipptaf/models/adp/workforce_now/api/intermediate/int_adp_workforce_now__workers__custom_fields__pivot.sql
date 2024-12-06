with
    from_item as (
        select
            associate_oid,
            date_value,
            indicator_value,
            number_value,
            string_value,
            code_value,

            regexp_replace(name_code__code_value, r'\W', '') as pivot_column,
        from {{ ref("int_adp_workforce_now__workers__custom_fields") }}
    )

select
    associate_oid,

    date_value_wfmgrloareturndate as wf_mgr_loa_return_date,

    indicator_value_receivedsignonbonus as received_sign_on_bonus,
    indicator_value_wfmgrloa as wf_mgr_loa,

    string_value_miamiacesnumber as miami_aces_number,
    string_value_njpensionnumber as nj_pension_number,
    string_value_wfmgrtrigger as wf_mgr_trigger,

    code_value_preferredraceethnicity as preferred_race_ethnicity,
    code_value_remoteworkstatus as remote_work_status,
    code_value_teacherprepprogram as teacher_prep_program,
    code_value_wfmgraccrualprofile as wf_mgr_accrual_profile,
    code_value_wfmgreetype as wf_mgr_ee_type,
    code_value_wfmgrhomehyperfind as wf_mgr_home_hyperfind,
    code_value_wfmgrpayrule as wf_mgr_pay_rule,
    code_value_lifeexperienceincommunitiesweserve
    as life_experience_in_communities_we_serve,
    code_value_professionalexperienceincommunitiesweserve
    as professional_experience_in_communities_we_serve,

    safe_cast(string_value_employeenumber as int) as employee_number,
    safe_cast(string_value_wfmgrbadgenumber as int) as wf_mgr_badge_number,
from
    from_item pivot (
        max(date_value) as date_value,
        max(indicator_value) as indicator_value,
        max(number_value) as number_value,
        max(string_value) as string_value,
        max(code_value) as code_value
        for pivot_column in (
            'EmployeeNumber',
            'LifeExperienceinCommunitiesWeServe',
            'MiamiACESNumber',
            'NJPensionNumber',
            'PreferredRaceEthnicity',
            'ProfessionalExperienceinCommunitiesWeServe',
            'ReceivedSignOnBonus',
            'RemoteWorkStatus',
            'TeacherPrepProgram',
            'WFMgrAccrualProfile',
            'WFMgrBadgeNumber',
            'WFMgrEEType',
            'WFMgrHomeHyperfind',
            'WFMgrLOA',
            'WFMgrLOAReturnDate',
            'WFMgrPayRule',
            'WFMgrTrigger'
        )
    )
