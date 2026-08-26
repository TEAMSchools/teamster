with
    staff_roster as (
        select
            employee_number,
            given_name,
            family_name_1,
            powerschool_teacher_number,
            user_principal_name,
            sam_account_name,
            home_business_unit_name,
            home_work_location_reporting_name,
            home_work_location_powerschool_school_id,
            home_work_location_dagster_code_location,
            home_department_name,
            job_title,
        from {{ ref("int_people__staff_roster") }}
        where
            not is_prestart
            and worker_status_code != 'Terminated'
            -- Miami rosters into Clever directly from Focus; excluded from all
            -- six feeds
            and home_work_location_dagster_code_location != 'kippmiami'

        union all

        select
            null as employee_number,

            given_name,
            sn as family_name_1,
            employee_id as powerschool_teacher_number,
            user_principal_name,
            sam_account_name,
            company as home_business_unit_name,
            physical_delivery_office_name as home_work_location_reporting_name,
            powerschool_school_id as home_work_location_powerschool_school_id,
            dagster_code_location as home_work_location_dagster_code_location,
            department as home_department_name,
            title as job_title,
        from {{ ref("int_people__temp_staff") }}
        where
            dagster_code_location != 'kippmiami'
            -- int_people__temp_staff gates on idauto_status and the AD account
            -- flag, neither of which flips on offboarding. A populated
            -- idauto_person_term_date is the only termination signal it carries.
            and idauto_person_term_date is null
    ),

    schools as (
        select
            schoolstate,

            cast(school_number as string) as school_id,

            regexp_extract(
                _dbt_source_relation, r'(kipp\w+)_'
            ) as dagster_code_location,
        from {{ ref("stg_powerschool__schools") }}
        where
            state_excludefromreporting = 0
            and _dbt_source_relation not like '%kippmiami%'
    ),

    assignments as (
        /* School and campus staff assigned to their primary school only. The
           campus crosswalk previously overrode the school id here, but it
           resolved to the same value the roster already carries.
        */
        select
            sr.powerschool_teacher_number,
            sr.user_principal_name,
            sr.given_name,
            sr.family_name_1,
            sr.home_department_name,
            sr.sam_account_name,

            cast(sr.home_work_location_powerschool_school_id as string) as school_id,
        from staff_roster as sr
        where
            sr.home_department_name not in ('Data', 'Teaching and Learning')
            and sr.home_work_location_powerschool_school_id != 0

        union all

        select
            sr.powerschool_teacher_number,
            sr.user_principal_name,
            sr.given_name,
            sr.family_name_1,
            sr.home_department_name,
            sr.sam_account_name,

            sch.school_id,
        from staff_roster as sr
        cross join schools as sch
        where
            sr.home_business_unit_name = 'KIPP TEAM and Family Schools Inc.'
            and (
                sr.home_department_name
                in ('Data', 'Teaching and Learning', 'Executive')
                or sr.job_title
                in ('Executive Director', 'Managing Director', 'Deputy Chief')
            )

        union all

        select
            sr.powerschool_teacher_number,
            sr.user_principal_name,
            sr.given_name,
            sr.family_name_1,
            sr.home_department_name,
            sr.sam_account_name,

            sch.school_id,
        from staff_roster as sr
        inner join
            schools as sch
            on sr.home_work_location_dagster_code_location = sch.dagster_code_location
        where sr.home_work_location_powerschool_school_id = 0

        union all

        select
            sr.powerschool_teacher_number,
            sr.user_principal_name,
            sr.given_name,
            sr.family_name_1,
            sr.home_department_name,
            sr.sam_account_name,

            sch.school_id,
        from {{ ref("stg_ldap__group") }} as g
        cross join unnest(g.member) as group_member_distinguished_name
        inner join
            {{ ref("stg_ldap__user_person") }} as up
            on group_member_distinguished_name = up.distinguished_name
        inner join staff_roster as sr on up.employee_number = sr.employee_number
        inner join schools as sch on sch.schoolstate = 'NJ'
        where g.cn = 'Group Staff NJ Regional'

        union all

        /* School Leader in Residence (Room 9, Newark) also covers Paterson
           schools -- #4981
        */
        select
            sr.powerschool_teacher_number,
            sr.user_principal_name,
            sr.given_name,
            sr.family_name_1,
            sr.home_department_name,
            sr.sam_account_name,

            sch.school_id,
        from staff_roster as sr
        inner join
            schools as sch
            on sch.dagster_code_location in ('kippnewark', 'kipppaterson')
        where
            sr.job_title = 'School Leader in Residence'
            and sr.home_work_location_reporting_name = 'Room 9'
    )

select distinct  /* some staff are in multiple assignment groups */
    school_id,
    powerschool_teacher_number as staff_id,
    user_principal_name as staff_email,
    given_name as first_name,
    family_name_1 as last_name,
    home_department_name as department,

    'School Admin' as title,

    sam_account_name as username,

    null as `password`,

    if(home_department_name = 'Operations', 'School Tech Lead', null) as `role`,
from assignments
