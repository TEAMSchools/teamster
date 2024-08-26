with
    from_item as (
        select
            associate_oid,
            name_code__code_value,
            date_value,
            indicator_value,
            number_value,
            string_value,
            code_value,
        from {{ ref("int_adp_workforce_now__workers__custom_fields") }}
    )

select
    associate_oid,

    string_value_employeenumber as employee_number,
    code_value_lifeexperienceincommunitiesweserve
    as life_experience_in_communities_we_serve,
    string_value_miamiacesnumber as miami_aces_number,
    string_value_njpensionnumber as nj_pension_number,
    code_value_preferredraceethnicity as preferred_race_ethnicity,
    code_value_professionalexperienceincommunitiesweserve
    as professional_experience_in_communities_we_serve,
    indicator_value_receivedsignonbonus as received_sign_on_bonus,
    code_value_remoteworkstatus as remote_work_status,
    code_value_teacherprepprogram as teacher_prep_program,
    code_value_wfmgraccrualprofile as wf_mgr_accrual_profile,
    string_value_wfmgrbadgenumber as wf_mgr_badge_number,
    code_value_wfmgreetype as wf_mgr_ee_type,
    code_value_wfmgrhomehyperfind as wf_mgr_home_hyperfind,
    indicator_value_wfmgrloa as wf_mgr_loa,
    date_value_wfmgrloareturndate as wf_mgr_loa_return_date,
    code_value_wfmgrpayrule as wf_mgr_pay_rule,
    string_value_wfmgrtrigger as wf_mgr_trigger,
from
    from_item pivot (
        max(date_value) as date_value,
        max(indicator_value) as indicator_value,
        max(number_value) as number_value,
        max(string_value) as string_value,
        max(code_value) as code_value
        for regexp_replace(name_code__code_value, r'\W', '') in (
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
