{{ config(enabled=False) }}

with
    roles as (
        select user_id, dbo.group_concat(role_name) as roles
        from
            (
                select urm.user_id, r.`name` as role_name
                from coupa.user_role_mapping as urm
                inner join coupa.role as r on urm.role_id = r.id

                union

                select u.id as user_id, 'Expense User' as role_name
                from coupa.user as u
            ) as sub
        group by user_id
    ),

    business_groups as (
        select ubgm.user_id, dbo.group_concat_d(bg.name, ', ') as business_group_names
        from coupa.user_business_group_mapping as ubgm
        inner join coupa.business_group as bg on ubgm.business_group_id = bg.id
        group by ubgm.user_id
    ),

    all_users as (
        /* existing users */
        select
            sr.employee_number,
            sr.first_name,
            sr.last_name,
            sr.position_status,
            sr.business_unit_code,
            sr.home_department,
            sr.job_title,
            sr.location,
            sr.worker_category,
            sr.wfmgr_pay_rule,
            cu.active,
            case
                when cu.purchasing_user = 1
                then 'Yes'
                when cu.purchasing_user = 0
                then 'No'
            end as purchasing_user,
            r.roles,
            bg.business_group_names as content_groups
        from {{ ref("base_people__staff_roster") }} as sr
        inner join coupa.user as cu on sr.employee_number = cu.employee_number
        inner join roles as r on cu.id = r.user_id
        left join business_groups as bg on cu.id = bg.user_id
        where
            sr.position_status != 'Prestart'
            and coalesce(sr.termination_date, cast(current_timestamp as date))
            >= datefromparts(utilities.global_academic_year() - 1, 7, 1)
            and isnull (sr.worker_category, '') not in ('Intern', 'Part Time')
            and isnull (sr.wfmgr_pay_rule, '') != 'PT Hourly'

        union all

        /* new users */
        select
            sr.employee_number,
            sr.first_name,
            sr.last_name,
            sr.position_status,
            sr.business_unit_code,
            sr.home_department,
            sr.job_title,
            sr.location,
            sr.worker_category,
            sr.wfmgr_pay_rule,
            1 as active,
            'No' as purchasing_user,
            'Expense User' as roles,
            null as content_groups
        from {{ ref("base_people__staff_roster") }} as sr
        left join coupa.user as cu on sr.employee_number = cu.employee_number
        where
            sr.position_status not in ('Prestart', 'Terminated')
            and isnull (sr.worker_category, '') not in ('Intern', 'Part Time')
            and isnull (sr.wfmgr_pay_rule, '') != 'PT Hourly'
            and cu.employee_number is null
    ),

    sub as (
        select
            au.employee_number,
            au.first_name,
            au.last_name,
            au.roles,
            au.position_status,
            au.active,
            au.purchasing_user,
            au.content_groups,
            au.business_unit_code,
            au.worker_category,
            au.wfmgr_pay_rule,
            a.location_code,
            a.street_1,
            a.city,
            a.state,
            a.postal_code,
            a.name as address_name,
            case
                /* no interns */
                when au.worker_category = 'Intern'
                then 'inactive'
                /* keep Approvers active while on leave */
                when
                    (
                        au.position_status = 'Leave'
                        and (
                            au.roles like '%Edit Expense Report AS Approver%'
                            or au.roles like '%Edit Requisition AS Approver%'
                        )
                    )
                then 'active'
                /* deactivate all others on leave */
                when au.position_status = 'Leave'
                then 'inactive'
                when ad.is_active = 1
                then 'active'
                else 'inactive'
            end as coupa_status,
            lower(ad.samaccountname) as samaccountname,
            lower(ad.userprincipalname) as userprincipalname,
            lower(ad.mail) as mail,
            case when a.street_2 != '' then a.street_2 end as street_2,
            case when a.attention != '' then a.attention end as attention,

            /*
              override
              > lookup table (content group/department/job)
              > lookup table (content group/department)
            */
            coalesce(
                x.coupa_school_name,
                case
                    when (sn.coupa_school_name = '<Use PhysicalDeliveryOfficeName>')
                    then ad.physicaldeliveryofficename
                    else sn.coupa_school_name
                end,
                case
                    when (sn2.coupa_school_name = '<Use PhysicalDeliveryOfficeName>')
                    then ad.physicaldeliveryofficename
                    else sn2.coupa_school_name
                end
            ) as coupa_school_name
        from all_users as au
        inner join
            adsi.user_attributes_static as ad
            on au.employee_number = ad.employeenumber
            and isnumeric(ad.employeenumber) = 1
        left join
            coupa.school_name_lookup as sn
            on au.business_unit_code = sn.business_unit_code
            and au.home_department = sn.home_department
            and au.job_title = sn.job_title
        left join
            coupa.school_name_lookup as sn2
            on au.business_unit_code = sn2.business_unit_code
            and au.home_department = sn2.home_department
            and sn2.job_title = 'Default'
        left join coupa.user_exceptions as x on au.employee_number = x.employee_number
        left join coupa.address_name_crosswalk as anc on au.location = anc.adp_location
        left join
            coupa.address as a on anc.coupa_address_name = a.`name` and a.active = 1
    )

select
    sub.samaccountname as `login`,
    sub.userprincipalname as `sso identifier`,
    sub.mail as `email`,
    sub.first_name as `first name`,
    sub.last_name as `last name`,
    sub.employee_number as `employee number`,
    sub.roles as `user role names`,
    sub.location_code as `default address location code`,
    sub.street_1 as `default address street 1`,
    sub.street_2 as `default address street 2`,
    sub.city as `default address city`,
    sub.`state` as `default address state`,
    sub.postal_code as `default address postal code`,
    'US' as `default address country code`,
    sub.attention as `default address attention`,
    sub.address_name as `default address name`,
    sub.coupa_status as `status`,
    'SAML' as `authentication method`,
    'No' as `generate password and notify user`,
    case
        when sub.worker_category in ('Part Time', 'Intern')
        then 'No'
        when sub.wfmgr_pay_rule = 'PT Hourly'
        then 'No'
        when sub.coupa_status = 'inactive'
        then 'No'
        else 'Yes'
    end as `expense user`,
    /* preserve Coupa, otherwise No */
    coalesce(
        case when sub.coupa_status = 'inactive' then 'No' end, sub.purchasing_user, 'No'
    ) as `purchasing user`,
    /* preserve Coupa, otherwise use HRIS */
    coalesce(
        sub.content_groups,
        case
            when sub.business_unit_code = 'KIPP_TAF'
            then 'KIPP NJ'
            when sub.business_unit_code = 'KIPP_MIAMI'
            then 'MIA'
            else sub.business_unit_code
        end
    ) as `content groups`,
    concat(
        case when sub.position_status = 'Terminated' then 'X' end,
        utilities.strip_characters(concat(sub.first_name, sub.last_name), '^A-Z'),
        case
            when isnumeric(right(sub.samaccountname, 1)) = 1
            then right(sub.samaccountname, 1)
        end
    ) as `mention name`,
    case
        when sna.coupa_school_name = '<BLANK>'
        then null
        else coalesce(sna.coupa_school_name, sub.`coupa_school_name`)
    end as `school name`
from sub
left join
    coupa.school_name_aliases as sna
    on sub.coupa_school_name = sna.physical_delivery_office_name
