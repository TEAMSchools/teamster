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

            sc.region,
        from {{ ref("base_people__staff_roster") }} as sr
        inner join
            {{ ref("stg_people__location_crosswalk") }} as sc
            on sr.home_work_location_name = sc.name
        inner join
            {{ ref("stg_powerschool__users") }} as u
            on sr.powerschool_teacher_number = u.teachernumber
            and sr.home_work_location_powerschool_school_id = u.homeschoolid
            and sr.home_work_location_dagster_code_location
            = regexp_extract(u._dbt_source_relation, r'(kipp\w+)_\w+')
        where
            {# import terminated staff up to a week after termination date #}
            date_diff(
                current_date('America/New_York'),
                ifnull(sr.worker_termination_date, current_date('America/New_York')),
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

            sc.region,
        from {{ ref("base_people__staff_roster") }} as sr
        inner join
            {{ ref("stg_people__location_crosswalk") }} as sc
            on sr.home_work_location_name = sc.name
        left join
            {{ ref("stg_powerschool__users") }} as u
            on sr.powerschool_teacher_number = u.teachernumber
            and sr.home_work_location_dagster_code_location
            = regexp_extract(u._dbt_source_relation, r'(kipp\w+)_\w+')
        where
            {# import terminated staff up to a week after termination date #}
            date_diff(
                current_date('America/New_York'),
                ifnull(sr.worker_termination_date, current_date('America/New_York')),
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
            region,
            home_work_location_powerschool_school_id,
            birth_date,
            lower(sam_account_name) as sam_account_name,
            lower(mail) as mail,
            case
                when
                    date_diff(
                        current_date('America/New_York'),
                        ifnull(
                            worker_termination_date, current_date('America/New_York')
                        ),
                        day
                    )
                    <= 7
                then 1
                when assignment_status not in ('Terminated', 'Deceased')
                then 1
                when worker_termination_date >= current_date('America/New_York')
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
    region as legal_entity_name,
from user_status
