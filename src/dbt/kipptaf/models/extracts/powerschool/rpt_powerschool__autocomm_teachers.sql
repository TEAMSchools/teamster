with
    staff_roster as (
        select
            powerschool_teacher_number,
            given_name,
            family_name_1,
            home_work_location_name,
            home_work_location_powerschool_school_id,
            home_department_name,
            birth_date,
            worker_termination_date,
            sam_account_name,
            mail,
            assignment_status,
            home_work_location_dagster_code_location,

            date_diff(
                current_date('{{ var("local_timezone") }}'),
                coalesce(
                    worker_termination_date, current_date('{{ var("local_timezone") }}')
                ),
                day
            ) as days_after_termination,
        from {{ ref("int_people__staff_roster") }}
        where home_department_name != 'Data' or home_department_name is null

        union all

        select
            employee_id as powerschool_teacher_number,
            given_name,
            sn as family_name_1,
            physical_delivery_office_name as home_work_location_name,
            powerschool_school_id as home_work_location_powerschool_school_id,
            department as home_department_name,

            null as birth_date,
            null as worker_termination_date,

            sam_account_name,
            mail,

            'Active' as assignment_status,

            dagster_code_location as home_work_location_dagster_code_location,

            0 as days_after_termination,
        from {{ ref("int_people__temp_staff") }}
    ),

    users_union as (
        /* existing users: ADP-derived schoolid matches PS homeschoolid */
        select
            sr.powerschool_teacher_number,
            sr.given_name,
            sr.family_name_1,
            sr.home_work_location_name,
            sr.home_work_location_powerschool_school_id,
            sr.home_department_name,
            sr.worker_termination_date,
            sr.sam_account_name,
            sr.mail,
            sr.assignment_status,
            sr.home_work_location_dagster_code_location,
            sr.days_after_termination,

            coalesce(sr.birth_date, ucf.dob) as birth_date,
        from staff_roster as sr
        inner join
            {{ ref("stg_powerschool__users") }} as u
            on sr.powerschool_teacher_number = u.teachernumber
            and sr.home_work_location_powerschool_school_id = u.homeschoolid
            and sr.home_work_location_dagster_code_location = u.dagster_code_location
        left join
            {{ ref("stg_powerschool__userscorefields") }} as ucf
            on u.dcid = ucf.usersdcid
            and {{ union_dataset_join_clause(left_alias="u", right_alias="ucf") }}
        /* import terminated staff up to 2 weeks after termination date */
        where sr.days_after_termination <= 14

        union all

        /* new users: teachernumber does not exist in PS */
        select
            sr.powerschool_teacher_number,
            sr.given_name,
            sr.family_name_1,
            sr.home_work_location_name,
            sr.home_work_location_powerschool_school_id,
            sr.home_department_name,
            sr.worker_termination_date,
            sr.sam_account_name,
            sr.mail,
            sr.assignment_status,
            sr.home_work_location_dagster_code_location,
            sr.days_after_termination,
            sr.birth_date,
        from staff_roster as sr
        left join
            {{ ref("stg_powerschool__users") }} as u
            on sr.powerschool_teacher_number = u.teachernumber
            and sr.home_work_location_dagster_code_location = u.dagster_code_location
        where sr.days_after_termination <= 14 and u.dcid is null
    ),

    user_status as (
        select
            powerschool_teacher_number,
            given_name,
            family_name_1,
            birth_date,
            home_work_location_powerschool_school_id,
            home_work_location_dagster_code_location,
            sam_account_name,
            mail,

            case
                when days_after_termination <= 14
                then 1
                when assignment_status not in ('Terminated', 'Deceased')
                then 1
                when
                    worker_termination_date
                    >= current_date('{{ var("local_timezone") }}')
                then 1
                else 2
            end as `status`,
        from users_union
    )

select
    powerschool_teacher_number as teachernumber,
    given_name as first_name,
    family_name_1 as last_name,
    mail as email_addr,
    `status`,
    home_work_location_dagster_code_location,

    format_date('%m/%d/%Y', birth_date) as dob,

    coalesce(home_work_location_powerschool_school_id, 0) as schoolid,
    coalesce(home_work_location_powerschool_school_id, 0) as homeschoolid,

    if(`status` = 1, sam_account_name, null) as loginid,
    if(`status` = 1, sam_account_name, null) as teacherloginid,
    if(`status` = 1, 1, 0) as teacherldapenabled,
    if(`status` = 1, 1, 0) as adminldapenabled,
    if(`status` = 1, 1, 0) as ptaccess,
    if(`status` = 1, 1, 0) as staffstatus,
from user_status
