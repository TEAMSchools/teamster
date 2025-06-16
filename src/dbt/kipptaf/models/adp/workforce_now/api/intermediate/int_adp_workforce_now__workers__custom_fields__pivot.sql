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

    indicator_value_receivedsignonbonus as received_sign_on_bonus,

    string_value_miamiacesnumber as miami_aces_number,
    string_value_njpensionnumber as nj_pension_number,

    code_value_preferredraceethnicity as preferred_race_ethnicity,
    code_value_remoteworkstatus as remote_work_status,
    code_value_teacherprepprogram as teacher_prep_program,
    code_value_lifeexperienceincommunitiesweserve
    as life_experience_in_communities_we_serve,
    code_value_professionalexperienceincommunitiesweserve
    as professional_experience_in_communities_we_serve,

    safe_cast(string_value_employeenumber as int) as employee_number,
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
            'TeacherPrepProgram'
        )
    )
