-- trunk-ignore(sqlfluff/ST06)
select
    -- trunk-ignore-begin(sqlfluff/RF05)
    student_number as `01 Import Student ID`,
    state_studentnumber as `02 State Student ID`,
    student_last_name as `03 Last Name`,
    student_first_name as `04 First Name`,
    student_middle_name as `05 Middle Name`,
    dob as `06 Birth Date`,

    null as `07 Gender`,
    null as `08 Primary Ethnicity`,
    null as `09 Secondary Ethnicity`,
    null as `10 Tertiary Ethnicity`,
    null as `11 Is Hispanic`,
    null as `12 Primary Language`,
    null as `13 Correspondence Language`,
    null as `14 English Proficiency`,
    null as `15 Redesignation Date`,

    case
        when special_education_code in ('PSD', 'CMO', 'CMI')
        then '210'
        when special_education_code in ('CI', 'ESLS')
        then '240'
        when special_education_code = 'VI'
        then '250'
        when special_education_code = 'ED'
        then '260'
        when special_education_code = 'OI'
        then '270'
        when special_education_code = 'OHI'
        then '280'
        when special_education_code = 'SLD'
        then '290'
        when special_education_code = 'MD'
        then '310'
        when special_education_code in ('AI', 'AUT')
        then '320'
        when special_education_code = 'TBI'
        then '330'
    end as `16 Primary Disability`,

    null as `17 Migrant Ed Student ID`,
    null as `18 Lep Date`,
    null as `19 Us Entry Date`,
    null as `20 School Enter Date`,
    null as `21 District Enter Date`,
    null as `22 Parent Education Level`,
    null as `23 Residential Status`,
    null as `24 Special Needs Status`,
    null as `25 Sst Date`,
    null as `26 Plan 504 Accommodations`,
    null as `27 Plan 504 Annual Review Date`,
    null as `28 Exit Date`,
    null as `29 Birth City`,
    null as `30 Birth State`,
    null as `31 Birth Country`,
    null as `32 Lunch ID`,

    concat(academic_year, '-', (academic_year + 1)) as `33 Academic Year`,

    null as `34 Name Suffix`,
    null as `35 Aka Last Name`,
    null as `36 Aka First Name`,
    null as `37 Aka Middle Name`,
    null as `38 Aka Name Suffix`,
    null as `39 Lunch Balance`,
    null as `40 Resident District Site ID`,
    null as `41 Operating District Site ID`,
    null as `42 Resident School Site ID`,
    null as `43 Birthdate Verification`,
    null as `44 Homeless Dwelling Type`,
    null as `45 Photo Release`,
    null as `46 Military Recruitment`,
    null as `47 Internet Release`,
    null as `48 Graduation Date`,
    null as `49 Graduation Status`,
    null as `50 Service Learning Hours`,
    null as `51 Us Abroad`,
    null as `52 Military Family`,
    null as `53 Home Address Verification Date`,
    null as `54 Entry Date`,
    null as `55 Secondary Disability`,
    null as `56 State School Entry Date`,
    null as `57 Us School Entry Date`,
    null as `58 Local Student ID`,
    null as `59 School Student ID`,
    null as `60 Other Student ID`,
    null as `61 Graduation Requirement Year`,
    null as `62 Next School Site ID`,
    null as `63 Prior District`,
    null as `64 Prior School`,
-- trunk-ignore-end(sqlfluff/RF05)
from {{ ref("int_extracts__student_enrollments") }}
where academic_year = {{ current_school_year(var("local_timezone")) }} and rn_year = 1
