with
    roles_union as (
        select user_id, role_name,
        from {{ ref("stg_coupa__users__roles") }}

        union distinct

        select id as user_id, 'Expense User' as role_name,
        from {{ ref("stg_coupa__users") }}
    ),

    roles as (
        select user_id, string_agg(role_name order by role_name asc) as roles,
        from roles_union
        group by user_id
    ),

    business_groups as (
        select
            user_id,

            string_agg(
                content_group_name order by content_group_name asc
            ) as business_group_names,
        from {{ ref("stg_coupa__users__content_groups") }}
        group by user_id
    ),

    all_users as (
        /* existing users */
        select
            sr.employee_number,
            sr.legal_given_name,
            sr.legal_family_name,
            sr.assignment_status,
            sr.home_business_unit_code,
            sr.home_department_name,
            sr.job_title,
            sr.home_work_location_name,
            sr.uac_account_disable,
            sr.physical_delivery_office_name,
            sr.sam_account_name,
            sr.user_principal_name,
            sr.mail,

            cu.active,

            r.roles,

            bg.business_group_names as content_groups,

            date_diff(
                current_date('{{ var("local_timezone") }}'),
                sr.worker_termination_date,
                day
            ) as days_terminated,

            if(cu.purchasing_user, 'Yes', 'No') as purchasing_user,
        from {{ ref("int_people__staff_roster") }} as sr
        inner join
            {{ ref("stg_coupa__users") }} as cu
            on sr.employee_number = cu.employee_number
        inner join roles as r on cu.id = r.user_id
        left join business_groups as bg on cu.id = bg.user_id
        where
            not sr.is_prestart
            and coalesce(
                sr.worker_termination_date, current_date('{{ var("local_timezone") }}')
            )
            >= '{{ var("current_academic_year") - 1 }}-07-01'
            and not regexp_contains(sr.worker_type_code, r'Part Time|Intern')

        union all

        /* new users */
        select
            sr.employee_number,
            sr.legal_given_name,
            sr.legal_family_name,
            sr.assignment_status,
            sr.home_business_unit_code,
            sr.home_department_name,
            sr.job_title,
            sr.home_work_location_name,
            sr.uac_account_disable,
            sr.physical_delivery_office_name,
            sr.sam_account_name,
            sr.user_principal_name,
            sr.mail,

            true as active,
            'Expense User' as roles,
            null as content_groups,
            null as days_terminated,
            'No' as purchasing_user,
        from {{ ref("int_people__staff_roster") }} as sr
        left join
            {{ ref("stg_coupa__users") }} as cu
            on sr.employee_number = cu.employee_number
        where
            not sr.is_prestart
            and sr.worker_status_code != 'Terminated'
            and not regexp_contains(sr.worker_type_code, r'Part Time|Intern')
            and cu.employee_number is null
    ),

    sub as (
        select
            au.employee_number,
            au.legal_given_name,
            au.legal_family_name,
            au.roles,
            au.assignment_status,
            au.active,
            au.purchasing_user,
            au.content_groups,
            au.home_business_unit_code,
            au.home_work_location_name,
            au.home_department_name,
            au.job_title,
            au.sam_account_name,
            au.user_principal_name,
            au.mail,
            au.days_terminated,

            x.sage_intacct_department,

            a.location_code,
            a.name as address_name,
            a.attention,
            a.street1 as street_1,
            a.street2 as street_2,
            a.city,
            a.state,
            a.postal_code,

            case
                when au.uac_account_disable = 0
                then 'active'
                when au.days_terminated <= 7
                then 'active'
                else 'inactive'
            end as coupa_status,

            {#
            > override
            >> lookup table (content group/department/job)
            >>> lookup table (content group/department)
            #}
            coalesce(
                x.coupa_school_name,
                if(
                    sn.coupa_school_name = '<Use PhysicalDeliveryOfficeName>',
                    au.physical_delivery_office_name,
                    sn.coupa_school_name
                ),
                if(
                    sn2.coupa_school_name = '<Use PhysicalDeliveryOfficeName>',
                    au.physical_delivery_office_name,
                    sn2.coupa_school_name
                )
            ) as coupa_school_name,
        from all_users as au
        left join
            {{ ref("stg_coupa__school_name_lookup") }} as sn
            on au.home_business_unit_code = sn.adp_business_unit_home_code
            and au.home_department_name = sn.adp_department_home_name
            and au.job_title = sn.adp_job_title
        left join
            {{ ref("stg_coupa__school_name_lookup") }} as sn2
            on au.home_business_unit_code = sn2.adp_business_unit_home_code
            and au.home_department_name = sn2.adp_department_home_name
            and sn2.adp_job_title = 'Default'
        left join
            {{ ref("stg_coupa__user_exceptions") }} as x
            on au.employee_number = x.employee_number
        left join
            {{ ref("stg_coupa__address_name_crosswalk") }} as anc
            on coalesce(x.home_work_location_name, au.home_work_location_name)
            = anc.adp_home_work_location_name
        left join
            {{ ref("stg_coupa__addresses") }} as a
            on anc.coupa_address_name = a.name
            and a.active
    )

select
    sub.sam_account_name as `Login`,
    sub.user_principal_name as `Sso Identifier`,
    sub.mail as `Email`,
    sub.legal_given_name as `First Name`,
    sub.legal_family_name as `Last Name`,
    sub.employee_number as `Employee Number`,
    sub.roles as `User Role Names`,
    sub.location_code as `Default Address Location Code`,
    sub.street_1 as `Default Address Street 1`,
    sub.street_2 as `Default Address Street 2`,
    sub.city as `Default Address City`,
    sub.state as `Default Address State`,
    sub.postal_code as `Default Address Postal Code`,
    sub.attention as `Default Address Attention`,
    sub.address_name as `Default Address Name`,
    sub.coupa_status as `Status`,
    sub.employee_number as `Sage Intacct ID`,

    ifl.sage_intacct_fund as `Sage Intacct Fund`,

    'US' as `Default Address Country Code`,
    'SAML' as `Authentication Method`,
    'No' as `Generate Password And Notify User`,
    'CoupaPay' as `Employee Payment Channel`,

    if(sub.coupa_status = 'inactive', 'No', 'Yes') as `Expense User`,

    case
        when sub.coupa_status = 'inactive'
        then 'No'
        when sub.assignment_status = 'Leave'
        then 'No'
        when sub.days_terminated >= 0
        then 'No'
        when sub.coupa_status != 'inactive'
        then sub.purchasing_user
        else 'No'
    end as `Purchasing User`,

    /* preserve Coupa, otherwise use HRIS */
    coalesce(
        sub.content_groups,
        case
            sub.home_business_unit_code
            when 'KIPP_TAF'
            then 'KTAF'
            when 'KIPP_MIAMI'
            then 'MIA'
            else sub.home_business_unit_code
        end
    ) as `Content Groups`,

    concat(
        if(sub.assignment_status = 'Terminated', 'X', ''),
        coalesce(
            regexp_replace(
                concat(sub.legal_given_name, sub.legal_family_name), r'[^A-Za-z0-9]', ''
            ),
            ''
        ),
        coalesce(regexp_extract(sub.sam_account_name, r'\d+$'), '')
    ) as `Mention Name`,

    if(
        sna.coupa_school_name = '<BLANK>',
        null,
        coalesce(sna.coupa_school_name, sub.coupa_school_name)
    ) as `School Name`,

    coalesce(
        ipl1.sage_intacct_program, ipl2.sage_intacct_program
    ) as `Sage Intacct Program`,

    coalesce(
        sub.sage_intacct_department,
        idl1.sage_intacct_department,
        idl2.sage_intacct_department
    ) as `Sage Intacct Department`,

    coalesce(
        if(
            ill1.sage_intacct_location = '<ADP Home Work Location Name>',
            ipl1.sage_intacct_location,
            safe_cast(ill1.sage_intacct_location as int)
        ),
        if(
            ill2.sage_intacct_location = '<ADP Home Work Location Name>',
            ipl1.sage_intacct_location,
            safe_cast(ill2.sage_intacct_location as int)
        ),
        if(
            ill3.sage_intacct_location = '<ADP Home Work Location Name>',
            ipl1.sage_intacct_location,
            safe_cast(ill3.sage_intacct_location as int)
        )
    ) as `Sage Intacct Location`,
from sub
left join
    {{ ref("stg_coupa__school_name_crosswalk") }} as sna
    on sub.coupa_school_name = sna.ldap_physical_delivery_office_name
left join
    {{ ref("stg_coupa__intacct_fund_lookup") }} as ifl
    on sub.home_business_unit_code = ifl.adp_business_unit_home_code
left join
    {{ ref("stg_coupa__intacct_program_lookup") }} as ipl1
    on sub.home_business_unit_code = ipl1.adp_business_unit_home_code
    and sub.home_work_location_name = ipl1.adp_home_work_location_name
left join
    {{ ref("stg_coupa__intacct_program_lookup") }} as ipl2
    on sub.home_business_unit_code = ipl2.adp_business_unit_home_code
    and ipl2.adp_home_work_location_name = 'Default'
left join
    {{ ref("stg_coupa__intacct_department_lookup") }} as idl1
    on sub.home_business_unit_code = idl1.adp_business_unit_home_code
    and sub.home_department_name = idl1.adp_department_home_name
    and sub.job_title = idl1.adp_job_title
left join
    {{ ref("stg_coupa__intacct_department_lookup") }} as idl2
    on sub.home_business_unit_code = idl2.adp_business_unit_home_code
    and sub.home_department_name = idl2.adp_department_home_name
    and idl2.adp_job_title = 'Default'
left join
    {{ ref("stg_coupa__intacct_location_lookup") }} as ill1
    on sub.home_business_unit_code = ill1.adp_business_unit_home_code
    and sub.home_department_name = ill1.adp_department_home_name
    and sub.job_title = ill1.adp_job_title
left join
    {{ ref("stg_coupa__intacct_location_lookup") }} as ill2
    on sub.home_business_unit_code = ill2.adp_business_unit_home_code
    and sub.home_department_name = ill2.adp_department_home_name
    and ill2.adp_job_title = 'Default'
left join
    {{ ref("stg_coupa__intacct_location_lookup") }} as ill3
    on sub.home_business_unit_code = ill3.adp_business_unit_home_code
    and ill3.adp_department_home_name = 'Default'
    and ill3.adp_job_title = 'Default'
