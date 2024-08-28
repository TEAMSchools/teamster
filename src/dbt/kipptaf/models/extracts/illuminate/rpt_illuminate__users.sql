-- trunk-ignore(sqlfluff/ST06)
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    powerschool_teacher_number as `01 User ID`,
    family_name_1 as `02 User Last Name`,
    given_name as `03 User First Name`,

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

    home_business_unit as `18 City`,

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
from {{ ref("int_people__staff_roster") }}
