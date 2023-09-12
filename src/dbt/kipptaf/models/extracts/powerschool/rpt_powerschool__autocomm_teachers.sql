with
    users_union as (
        {# existing users: ADP-derived schoolid matches PS homeschoolid #}
        select
            sr.powerschool_teacher_number,
            sr.preferred_name_given_name,
            sr.preferred_name_family_name,
            sr.home_work_location_name,
            sr.home_work_location_powerschool_school_id,
            sr.department_home_name,
            sr.birth_date,
            sr.worker_termination_date,
            sr.sam_account_name,
            sr.mail,
            sr.assignment_status,
            sr.home_work_location_dagster_code_location,
        from {{ ref("base_people__staff_roster") }} as sr
        inner join
            {{ ref("stg_powerschool__users") }} as u
            on sr.powerschool_teacher_number = u.teachernumber
            and sr.home_work_location_powerschool_school_id = u.homeschoolid
            and sr.home_work_location_dagster_code_location
            = regexp_extract(u._dbt_source_relation, r'(kipp\w+)_')
        where
            {# import terminated staff up to a week after termination date #}
            date_diff(
                current_date('{{ var("local_timezone") }}'),
                ifnull(
                    sr.worker_termination_date,
                    current_date('{{ var("local_timezone") }}')
                ),
                day
            )
            <= 14
            and (sr.department_home_name != 'Data' or sr.department_home_name is null)

        union all

        {# new users: teachernumber does not exist in PS #}
        select
            sr.powerschool_teacher_number,
            sr.preferred_name_given_name,
            sr.preferred_name_family_name,
            sr.home_work_location_name,
            sr.home_work_location_powerschool_school_id,
            sr.department_home_name,
            sr.birth_date,
            sr.worker_termination_date,
            sr.sam_account_name,
            sr.mail,
            sr.assignment_status,
            sr.home_work_location_dagster_code_location,
        from {{ ref("base_people__staff_roster") }} as sr
        left join
            {{ ref("stg_powerschool__users") }} as u
            on sr.powerschool_teacher_number = u.teachernumber
            and sr.home_work_location_dagster_code_location
            = regexp_extract(u._dbt_source_relation, r'(kipp\w+)_')
        where
            {# import terminated staff up to a week after termination date #}
            date_diff(
                current_date('{{ var("local_timezone") }}'),
                ifnull(
                    sr.worker_termination_date,
                    current_date('{{ var("local_timezone") }}')
                ),
                day
            )
            <= 14
            and (sr.department_home_name != 'Data' or sr.department_home_name is null)
            and u.dcid is null
    ),

    user_status as (
        select
            powerschool_teacher_number,
            preferred_name_given_name,
            preferred_name_family_name,
            birth_date,
            home_work_location_powerschool_school_id,
            home_work_location_dagster_code_location,
            lower(sam_account_name) as sam_account_name,
            lower(mail) as mail,
            case
                when
                    date_diff(
                        current_date('{{ var("local_timezone") }}'),
                        ifnull(
                            worker_termination_date,
                            current_date('{{ var("local_timezone") }}')
                        ),
                        day
                    )
                    <= 7
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
    preferred_name_given_name as first_name,
    preferred_name_family_name as last_name,
    if(`status` = 1, sam_account_name, null) as loginid,
    if(`status` = 1, sam_account_name, null) as teacherloginid,
    mail as email_addr,
    coalesce(home_work_location_powerschool_school_id, 0) as schoolid,
    coalesce(home_work_location_powerschool_school_id, 0) as homeschoolid,
    `status`,
    if(`status` = 1, 1, 0) as teacherldapenabled,
    if(`status` = 1, 1, 0) as adminldapenabled,
    if(`status` = 1, 1, 0) as ptaccess,
    format_date('%m/%d/%Y', birth_date) as dob,
    home_work_location_dagster_code_location,
    2 as staffstatus,
from user_status
