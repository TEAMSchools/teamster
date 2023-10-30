with
    roles_union as (
        select urm.user_id, r.name as role_name,
        from {{ source("coupa", "user_role_mapping") }} as urm
        inner join {{ source("coupa", "role") }} as r on urm.role_id = r.id

        union distinct

        select u.id as user_id, 'Expense User' as role_name,
        from {{ source("coupa", "user") }} as u
    ),

    roles as (
        select user_id, string_agg(role_name) as roles,
        from roles_union
        group by user_id
    ),

    business_groups as (
        select ubgm.user_id, string_agg(bg.name, ', ') as business_group_names,
        from {{ source("coupa", "user_business_group_mapping") }} as ubgm
        inner join
            {{ source("coupa", "business_group") }} as bg
            on ubgm.business_group_id = bg.id
        group by ubgm.user_id
    ),

    all_users as (
        /* existing users */
        select
            sr.employee_number,
            sr.legal_name_given_name,
            sr.legal_name_family_name,
            sr.assignment_status,
            sr.business_unit_home_code,
            sr.department_home_name,
            sr.job_title,
            sr.home_work_location_name,
            sr.worker_type,
            sr.custom_wfmgr_pay_rule,
            sr.uac_account_disable,
            sr.physical_delivery_office_name,
            lower(sr.sam_account_name) as sam_account_name,
            lower(sr.user_principal_name) as user_principal_name,
            lower(sr.mail) as mail,

            cu.active,
            case
                when cu.purchasing_user then 'Yes' when not cu.purchasing_user then 'No'
            end as purchasing_user,

            r.roles,

            bg.business_group_names as content_groups,
        from {{ ref("base_people__staff_roster") }} as sr
        inner join
            {{ source("coupa", "user") }} as cu
            on sr.employee_number = safe_cast(cu.employee_number as int)
        inner join roles as r on cu.id = r.user_id
        left join business_groups as bg on cu.id = bg.user_id
        where
            not sr.is_prestart
            and coalesce(
                sr.worker_termination_date, current_date('{{ var("local_timezone") }}')
            )
            >= date({{ var("current_fiscal_year") }} - 2, 7, 1)
            and not regexp_contains(sr.worker_type, r'Part Time|Intern')
            and (
                sr.custom_wfmgr_pay_rule != 'PT Hourly'
                or sr.custom_wfmgr_pay_rule is null
            )

        union all

        /* new users */
        select
            sr.employee_number,
            sr.legal_name_given_name,
            sr.legal_name_family_name,
            sr.assignment_status,
            sr.business_unit_home_code,
            sr.department_home_name,
            sr.job_title,
            sr.home_work_location_name,
            sr.worker_type,
            sr.custom_wfmgr_pay_rule,
            sr.uac_account_disable,
            sr.physical_delivery_office_name,
            lower(sr.sam_account_name) as sam_account_name,
            lower(sr.user_principal_name) as user_principal_name,
            lower(sr.mail) as mail,

            true as active,
            'No' as purchasing_user,
            'Expense User' as roles,
            null as content_groups,
        from {{ ref("base_people__staff_roster") }} as sr
        left join
            {{ source("coupa", "user") }} as cu
            on sr.employee_number = safe_cast(cu.employee_number as int)
        where
            not sr.is_prestart
            and sr.assignment_status not in ('Terminated', 'Deceased')
            and not regexp_contains(sr.worker_type, r'Part Time|Intern')
            and (
                sr.custom_wfmgr_pay_rule != 'PT Hourly'
                or sr.custom_wfmgr_pay_rule is null
            )
            and cu.employee_number is null
    ),

    sub as (
        select
            au.employee_number,
            au.legal_name_given_name,
            au.legal_name_family_name,
            au.roles,
            au.assignment_status,
            au.active,
            au.purchasing_user,
            au.content_groups,
            au.business_unit_home_code,
            au.home_work_location_name,
            au.department_home_name,
            au.job_title,
            au.worker_type,
            au.custom_wfmgr_pay_rule,
            au.sam_account_name,
            au.user_principal_name,
            au.mail,
            case
                /* no interns */
                when au.worker_type like 'Intern%'
                then 'inactive'
                /* keep Approvers active while on leave */
                when
                    au.assignment_status = 'Leave'
                    and (
                        au.roles like '%Edit Expense Report AS Approver%'
                        or au.roles like '%Edit Requisition AS Approver%'
                    )
                then 'active'
                /* deactivate all others on leave */
                when au.assignment_status = 'Leave'
                then 'inactive'
                when au.uac_account_disable = 0
                then 'active'
                else 'inactive'
            end as coupa_status,

            a.location_code,
            a.street_1,
            a.city,
            a.state,
            a.postal_code,
            a.name as address_name,
            nullif(a.street_2, '') as street_2,
            nullif(a.attention, '') as attention,

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
            {{ source("coupa", "src_coupa__school_name_lookup") }} as sn
            on au.business_unit_home_code = sn.adp_business_unit_home_code
            and au.department_home_name = sn.adp_department_home_name
            and au.job_title = sn.adp_job_title
        left join
            {{ source("coupa", "src_coupa__school_name_lookup") }} as sn2
            on au.business_unit_home_code = sn2.adp_business_unit_home_code
            and au.department_home_name = sn2.adp_department_home_name
            and sn2.adp_job_title = 'Default'
        left join
            {{ source("coupa", "src_coupa__user_exceptions") }} as x
            on au.employee_number = x.employee_number
        left join
            {{ source("coupa", "src_coupa__address_name_crosswalk") }} as anc
            on au.home_work_location_name = anc.adp_home_work_location_name
        left join
            {{ source("coupa", "address") }} as a
            on anc.coupa_address_name = a.name
            and a.active
    )

select  -- noqa: disable=ST06
    -- noqa: disable=RF05
    sub.sam_account_name as `Login`,
    sub.user_principal_name as `Sso Identifier`,
    sub.mail as `Email`,
    sub.legal_name_given_name as `First Name`,
    sub.legal_name_family_name as `Last Name`,
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

    case
        when regexp_contains(sub.worker_type, r'Part Time|Intern')
        then 'No'
        when sub.custom_wfmgr_pay_rule = 'PT Hourly'
        then 'No'
        when sub.coupa_status = 'inactive'
        then 'No'
        else 'Yes'
    end as `Expense User`,
    /* preserve Coupa, otherwise No */
    coalesce(
        if(sub.coupa_status = 'inactive', 'No', null), sub.purchasing_user, 'No'
    ) as `Purchasing User`,
    /* preserve Coupa, otherwise use HRIS */
    coalesce(
        sub.content_groups,
        case
            sub.business_unit_home_code
            when 'KIPP_TAF'
            then 'KTAF'
            when 'KIPP_MIAMI'
            then 'MIA'
            else sub.business_unit_home_code
        end
    ) as `Content Groups`,
    concat(
        if(sub.assignment_status = 'Terminated', 'X', ''),
        coalesce(
            regexp_replace(
                concat(sub.legal_name_given_name, sub.legal_name_family_name),
                r'[^A-Za-z0-9]',
                ''
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
        idl1.sage_intacct_department, idl2.sage_intacct_department
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
    {{ source("coupa", "src_coupa__school_name_crosswalk") }} as sna
    on sub.coupa_school_name = sna.ldap_physical_delivery_office_name
left join
    {{ source("coupa", "src_coupa__intacct_fund_lookup") }} as ifl
    on sub.business_unit_home_code = ifl.adp_business_unit_home_code
left join
    {{ source("coupa", "src_coupa__intacct_program_lookup") }} as ipl1
    on sub.business_unit_home_code = ipl1.adp_business_unit_home_code
    and sub.home_work_location_name = ipl1.adp_home_work_location_name
left join
    {{ source("coupa", "src_coupa__intacct_program_lookup") }} as ipl2
    on sub.business_unit_home_code = ipl2.adp_business_unit_home_code
    and ipl2.adp_home_work_location_name = 'Default'
left join
    {{ source("coupa", "src_coupa__intacct_department_lookup") }} as idl1
    on sub.business_unit_home_code = idl1.adp_business_unit_home_code
    and sub.department_home_name = idl1.adp_department_home_name
    and sub.job_title = idl1.adp_job_title
left join
    {{ source("coupa", "src_coupa__intacct_department_lookup") }} as idl2
    on sub.business_unit_home_code = idl2.adp_business_unit_home_code
    and sub.department_home_name = idl2.adp_department_home_name
    and idl2.adp_job_title = 'Default'
left join
    {{ source("coupa", "src_coupa__intacct_location_lookup") }} as ill1
    on sub.business_unit_home_code = ill1.adp_business_unit_home_code
    and sub.department_home_name = ill1.adp_department_home_name
    and sub.job_title = ill1.adp_job_title
left join
    {{ source("coupa", "src_coupa__intacct_location_lookup") }} as ill2
    on sub.business_unit_home_code = ill2.adp_business_unit_home_code
    and sub.department_home_name = ill2.adp_department_home_name
    and ill2.adp_job_title = 'Default'
left join
    {{ source("coupa", "src_coupa__intacct_location_lookup") }} as ill3
    on sub.business_unit_home_code = ill3.adp_business_unit_home_code
    and ill3.adp_department_home_name = 'Default'
    and ill3.adp_job_title = 'Default'
