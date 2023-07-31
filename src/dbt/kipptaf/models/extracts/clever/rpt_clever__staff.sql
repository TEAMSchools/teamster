with
    staff_union as (
        {#
            School staff assigned to primary school only
            Campus staff assigned to all schools at campus
        #}
        select
            sr.powerschool_teacher_number,
            sr.user_principal_name,
            sr.preferred_name_given_name,
            sr.preferred_name_family_name,
            sr.department_home_name,
            sr.sam_account_name,

            cast(
                coalesce(
                    ccw.powerschool_school_id,
                    sr.home_work_location_powerschool_school_id
                ) as string
            ) as school_id,
        from {{ ref("base_people__staff_roster") }} as sr
        left join
            {{ source("people", "src_people__campus_crosswalk") }} as ccw
            on sr.home_work_location_name = ccw.name
            and not ccw.is_pathways
        where
            sr.assignment_status not in ('Terminated', 'Deceased')
            and not sr.is_prestart
            and sr.department_home_name not in ('Data', 'Teaching and Learning')
            and coalesce(
                ccw.powerschool_school_id, sr.home_work_location_powerschool_school_id
            )
            != 0

        union all

        {# T&L/EDs/Data to all schools under CMO #}
        select
            sr.powerschool_teacher_number,
            sr.user_principal_name,
            sr.preferred_name_given_name,
            sr.preferred_name_family_name,
            sr.department_home_name,
            sr.sam_account_name,

            cast(sch.school_number as string) as school_id,
        from {{ ref("base_people__staff_roster") }} as sr
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on (sch.state_excludefromreporting = 0)
        where
            sr.assignment_status not in ('Terminated', 'Deceased')
            and not sr.is_prestart
            and sr.business_unit_home_name = 'KIPP TEAM and Family Schools Inc.'
            and (
                sr.department_home_name in ('Data', 'Teaching and Learning')
                or sr.job_title in ('Executive Director', 'Managing Director')
            )

        union all

        {# all region #}
        select
            sr.powerschool_teacher_number,
            sr.user_principal_name,
            sr.preferred_name_given_name,
            sr.preferred_name_family_name,
            sr.department_home_name,
            sr.sam_account_name,

            cast(sch.school_number as string) as school_id,
        from {{ ref("base_people__staff_roster") }} as sr
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on sr.home_work_location_dagster_code_location
            = regexp_extract(sch._dbt_source_relation, r'kipp\w+')
            and sch.state_excludefromreporting = 0
        where
            sr.assignment_status not in ('Terminated', 'Deceased')
            and not sr.is_prestart
            and (
                sr.job_title in (
                    'Assistant Superintendent',
                    'Head of Schools',
                    'Head of Schools in Residence',
                    'Managing Director'
                )
                or (
                    sr.department_home_name = 'Special Education'
                    and sr.job_title like '%Director%'
                )
            )

        union all

        {# all NJ #}
        select
            sr.powerschool_teacher_number,
            sr.user_principal_name,
            sr.preferred_name_given_name,
            sr.preferred_name_family_name,
            sr.department_home_name,
            sr.sam_account_name,

            cast(sch.school_number as string) as school_id,
        from {{ ref("stg_ldap__group") }} as g
        cross join unnest(g.member) as group_member_distinguished_name
        inner join
            {{ ref("stg_ldap__user_person") }} as up
            on group_member_distinguished_name = up.distinguished_name
        inner join
            {{ ref("base_people__staff_roster") }} as sr
            on up.employee_number = sr.employee_number
            and sr.assignment_status not in ('Terminated', 'Deceased')
            and not sr.is_prestart
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
    preferred_name_given_name as first_name,
    preferred_name_family_name as last_name,
    department_home_name as department,

    'School Admin' as title,

    sam_account_name as username,

    null as `password`,

    if(department_home_name = 'Operations', 'School Tech Lead', null) as `role`,
from staff_union
