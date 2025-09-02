with
    staff_union as (
        /*
            School staff assigned to primary school only
            Campus staff assigned to all schools at campus
        */
        select
            sr.powerschool_teacher_number,
            sr.user_principal_name,
            sr.given_name,
            sr.family_name_1,
            sr.home_department_name,
            sr.sam_account_name,

            cast(
                coalesce(
                    ccw.powerschool_school_id,
                    sr.home_work_location_powerschool_school_id
                ) as string
            ) as school_id,
        from {{ ref("int_people__staff_roster") }} as sr
        left join
            {{ ref("stg_people__campus_crosswalk") }} as ccw
            on sr.home_work_location_name = ccw.name
            and not ccw.is_pathways
        where
            not sr.is_prestart
            and sr.worker_status_code != 'Terminated'
            and sr.home_department_name not in ('Data', 'Teaching and Learning')
            and coalesce(
                ccw.powerschool_school_id, sr.home_work_location_powerschool_school_id
            )
            != 0

        union all

        /* T&L/EDs/Data to all schools under CMO */
        select
            sr.powerschool_teacher_number,
            sr.user_principal_name,
            sr.given_name,
            sr.family_name_1,
            sr.home_department_name,
            sr.sam_account_name,

            cast(sch.school_number as string) as school_id,
        from {{ ref("int_people__staff_roster") }} as sr
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on sch.state_excludefromreporting = 0
        where
            sr.home_business_unit_name = 'KIPP TEAM and Family Schools Inc.'
            and not sr.is_prestart
            and sr.worker_status_code != 'Terminated'
            and (
                sr.home_department_name
                in ('Data', 'Teaching and Learning', 'Executive')
                or sr.job_title
                in ('Executive Director', 'Managing Director', 'Deputy Chief')
            )

        union all

        /* all region */
        select
            sr.powerschool_teacher_number,
            sr.user_principal_name,
            sr.given_name,
            sr.family_name_1,
            sr.home_department_name,
            sr.sam_account_name,

            cast(sch.school_number as string) as school_id,
        from {{ ref("int_people__staff_roster") }} as sr
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on sr.home_work_location_dagster_code_location
            = regexp_extract(sch._dbt_source_relation, r'(kipp\w+)_')
            and sch.state_excludefromreporting = 0
        where
            not sr.is_prestart
            and sr.home_work_location_powerschool_school_id = 0
            and sr.worker_status_code != 'Terminated'

        union all

        /* all NJ */
        select
            sr.powerschool_teacher_number,
            sr.user_principal_name,
            sr.given_name,
            sr.family_name_1,
            sr.home_department_name,
            sr.sam_account_name,

            cast(sch.school_number as string) as school_id,
        from {{ ref("stg_ldap__group") }} as g
        cross join unnest(g.member) as group_member_distinguished_name
        inner join
            {{ ref("stg_ldap__user_person") }} as up
            on group_member_distinguished_name = up.distinguished_name
        inner join
            {{ ref("int_people__staff_roster") }} as sr
            on up.employee_number = sr.employee_number
            and not sr.is_prestart
            and sr.worker_status_code != 'Terminated'
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on sch.schoolstate = 'NJ'
            and sch.state_excludefromreporting = 0
        where g.cn = 'Group Staff NJ Regional'
    )

select
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
from staff_union
