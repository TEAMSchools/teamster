with
    users_union as (
        /* existing users: ADP-derived schoolid matches PS homeschoolid */
        select
            sr.powerschool_teacher_number,
            sr.given_name,
            sr.family_name_1,
            sr.home_work_location_name,
            sr.home_work_location_powerschool_school_id,
            sr.organizational_unit__home__department__name,
            sr.person__birth_date,
            sr.worker_dates__termination_date,
            sr.sam_account_name,
            sr.mail,
            sr.assignment_status__status_code__long_name,
            sr.home_work_location_dagster_code_location,
        from {{ ref("int_people__staff_roster") }} as sr
        inner join
            {{ ref("stg_powerschool__users") }} as u
            on sr.powerschool_teacher_number = u.teachernumber
            and sr.home_work_location_powerschool_school_id = u.homeschoolid
            and sr.home_work_location_dagster_code_location = u.dagster_code_location
        where
            /* import terminated staff up to a week after termination date */
            date_diff(
                current_date('{{ var("local_timezone") }}'),
                coalesce(
                    sr.worker_dates__termination_date,
                    current_date('{{ var("local_timezone") }}')
                ),
                day
            )
            <= 14
            and (
                sr.organizational_unit__home__department__name != 'Data'
                or sr.organizational_unit__home__department__name is null
            )

        union all

        /* new users: teachernumber does not exist in PS */
        select
            sr.powerschool_teacher_number,
            sr.given_name,
            sr.family_name_1,
            sr.home_work_location_name,
            sr.home_work_location_powerschool_school_id,
            sr.organizational_unit__home__department__name,
            sr.person__birth_date,
            sr.worker_dates__termination_date,
            sr.sam_account_name,
            sr.mail,
            sr.assignment_status__status_code__long_name,
            sr.home_work_location_dagster_code_location,
        from {{ ref("int_people__staff_roster") }} as sr
        left join
            {{ ref("stg_powerschool__users") }} as u
            on sr.powerschool_teacher_number = u.teachernumber
            and sr.home_work_location_dagster_code_location = u.dagster_code_location
        where
            /* import terminated staff up to a week after termination date */
            date_diff(
                current_date('{{ var("local_timezone") }}'),
                coalesce(
                    sr.worker_dates__termination_date,
                    current_date('{{ var("local_timezone") }}')
                ),
                day
            )
            <= 14
            and (
                sr.organizational_unit__home__department__name != 'Data'
                or sr.organizational_unit__home__department__name is null
            )
            and u.dcid is null
    ),

    user_status as (
        select
            powerschool_teacher_number,
            given_name,
            family_name_1,
            person__birth_date,
            home_work_location_powerschool_school_id,
            home_work_location_dagster_code_location,
            sam_account_name,
            mail,

            case
                when
                    date_diff(
                        current_date('{{ var("local_timezone") }}'),
                        coalesce(
                            worker_dates__termination_date,
                            current_date('{{ var("local_timezone") }}')
                        ),
                        day
                    )
                    <= 7
                then 1
                when
                    assignment_status__status_code__long_name
                    not in ('Terminated', 'Deceased')
                then 1
                when
                    worker_dates__termination_date
                    >= current_date('{{ var("local_timezone") }}')
                then 1
                else 2
            end as `status`,
        from users_union
    )

-- trunk-ignore(sqlfluff/ST06)
select
    powerschool_teacher_number as teachernumber,
    given_name as first_name,
    family_name_1 as last_name,

    if(`status` = 1, sam_account_name, null) as loginid,
    if(`status` = 1, sam_account_name, null) as teacherloginid,

    mail as email_addr,

    coalesce(home_work_location_powerschool_school_id, 0) as schoolid,
    coalesce(home_work_location_powerschool_school_id, 0) as homeschoolid,

    `status`,

    if(`status` = 1, 1, 0) as teacherldapenabled,
    if(`status` = 1, 1, 0) as adminldapenabled,
    if(`status` = 1, 1, 0) as ptaccess,

    format_date('%m/%d/%Y', person__birth_date) as dob,

    home_work_location_dagster_code_location,

    if(`status` = 1, 1, 0) as staffstatus,
from user_status
