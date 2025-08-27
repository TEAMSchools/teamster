with
    union_relations as (
        select
            employee_number,
            powerschool_teacher_number,
            family_name_1,
            given_name,
            user_principal_name,
            sam_account_name,
            uac_account_disable,
            home_business_unit_name,
            job_title,
        from {{ ref("int_people__staff_roster") }}

        union all

        select
            null as employee_number,

            teachernumber as powerschool_teacher_number,
            last_name as family_name_1,
            first_name as given_name,
            email_addr as user_principal_name,
            email_addr as sam_account_name,

            if(ptaccess = 1 or psaccess = 1, 0, 1) as uac_account_disable,

            'KIPP Paterson' as home_business_unit_name,

            title as job_title,
        from {{ ref("stg_powerschool__users") }}
        where _dbt_source_relation like '%kipppaterson%'
    )

-- trunk-ignore(sqlfluff/ST06)
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    powerschool_teacher_number as `01 User ID`,

    regexp_replace(normalize(family_name_1, nfd), r'\pM', '') as `02 User Last Name`,
    regexp_replace(normalize(given_name, nfd), r'\pM', '') as `03 User First Name`,

    null as `04 User Middle Name`,
    null as `05 Birth Date`,
    null as `06 Gender`,

    user_principal_name as `07 Email Address`,
    sam_account_name as `08 Username`,

    null as `09 Password`,

    employee_number as `10 State User Or Employee ID`,

    null as `11 Name Suffix`,
    null as `12 Former First Name`,
    null as `13 Former Middle Name`,
    null as `14 Former Last Name`,
    null as `15 Primary Race`,
    null as `16 User Is Hispanic`,
    null as `17 Address`,

    home_business_unit_name as `18 City`,

    null as `19 State`,
    null as `20 Zip`,

    job_title as `21 Job Title`,

    null as `22 Education Level`,
    null as `23 Hire Date`,
    null as `24 Exit Date`,

    if(uac_account_disable = 0, 1, 0) as `25 Active`,

    null as `26 Position Status`,
    null as `27 Total Years Edu Service`,
    null as `28 Total Year In District`,
    null as `29 Email2`,
    null as `30 Phone1`,
    null as `31 Phone2`,
-- trunk-ignore-end(sqlfluff/RF05)
from union_relations
