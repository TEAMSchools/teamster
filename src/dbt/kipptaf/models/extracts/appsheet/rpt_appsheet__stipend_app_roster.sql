with
    /* departments with chiefs */
    department_chiefs as (
        select
            sr1.department_home_name,
            sr1.preferred_name_lastfirst,
            sr1.employee_number as ktaf_approver,
        from {{ ref("base_people__staff_roster") }} as sr1
        where
            (
                sr1.job_title like '%Chief%Officer'
                or sr1.job_title like '%Chief%Strategist%'
            )
            and sr1.department_home_name <> 'Executive'
            and sr1.assignment_status in ('Active', 'Leave')
    ),

    /* chiefs/presidents above departments without chiefs*/
    other_chiefs as (
        select
            sr1.department_home_name,
            sr1.report_to_preferred_name_lastfirst,
            coalesce(
                max(
                    case
                        when sr2.job_title like '%Chief%Officer%'
                        then sr1.report_to_employee_number
                        when sr2.job_title like '%Chief%Strategist%'
                        then sr1.report_to_employee_number
                        when sr2.job_title like '%President%'
                        then sr1.report_to_employee_number
                    end
                ),
                null
            ) as ktaf_approver,
        from {{ ref("base_people__staff_roster") }} as sr1
        left join
            {{ ref("base_people__staff_roster") }} as sr2
            on sr1.report_to_employee_number = sr2.employee_number
        where
            sr1.business_unit_home_code = 'KIPP_TAF'
            and sr1.assignment_status in ('Active', 'Leave')
            and (sr2.job_title like '%Chief%' or sr2.job_title like '%President%')
            and sr1.department_home_name <> 'Executive'
            and sr1.department_home_name
            not in (select dc.department_home_name, from department_chiefs as dc)
        group by sr1.department_home_name, sr1.report_to_preferred_name_lastfirst
    ),

    /* combining all departments to one KTAF list of departments
    and Chief/President approvers*/
    ktaf_approvers as (
        select d.*,
        from department_chiefs as d
        union all
        select o.*,
        from other_chiefs as o
    ),

    /* selecting the MDO from each region*/
    mdo as (
        select
            lc.region,
            max(
                if(
                    sr.job_title = 'Managing Director of Operations',
                    sr.employee_number,
                    null
                )
            ) as mdo_employee_number,
        from {{ ref("base_people__staff_roster") }} as sr
        left join
            {{ ref("stg_people__location_crosswalk") }} as lc
            on sr.home_work_location_name = lc.name
        where sr.assignment_status = 'Active'
        group by lc.region
    ),

    /* assigning approval routes according to location, entity, manager's entity*/
    route_assignments as (
        select
            sr.employee_number,
            sr.payroll_group_code,
            sr.worker_id,
            sr.payroll_file_number,
            sr.position_id,
            sr.job_title,
            sr.home_work_location_name,
            sr.department_home_name,
            sr.preferred_name_lastfirst,
            sr.user_principal_name,
            sr.google_email,
            sr.assignment_status,
            sr.business_unit_home_name,
            sr.business_unit_home_code,
            sr.worker_termination_date,
            sr.report_to_employee_number as manager_employee_number,

            sr2.report_to_employee_number as grandmanager_employee_number,

            lc.dso_employee_number,
            lc.sl_employee_number,
            lc.head_of_school_employee_number,
            lc.mdso_employee_number,

            mdo.mdo_employee_number,

            k.ktaf_approver,

            coalesce(
                sr.home_work_location_abbreviation, sr.home_work_location_name
            ) as location_abbr,
            /* Route assignment determines approvers in app */
            case

                /* KTAF teammate with KTAF manager*/
                when sr.business_unit_home_code = 'KIPP_TAF'
                then 'KTAF'
                /* Non-KTAF teammate with KTAF manager*/
                when
                    sr.business_unit_home_code <> 'KIPP_TAF'
                    and sr2.business_unit_home_code = 'KIPP_TAF'
                then 'MDSO'
                /* Non-KTAF teammate with non-school location*/
                when
                    (
                        sr.home_work_location_name like '%Room%'
                        or sr.home_work_location_name like '%Campus%'
                    )
                    and sr.business_unit_home_code <> 'KIPP_TAF'

                then 'MDO'
                /* School-based teammate*/
                when
                    (
                        sr.home_work_location_name not like '%Room%'
                        or sr.home_work_location_name not like '%Campus%'
                    )
                    and sr.business_unit_home_code <> 'KIPP_TAF'
                then 'School'
            end as route,
            coalesce(cc.name, sr.home_work_location_name) as campus,
        from {{ ref("base_people__staff_roster") }} as sr
        left join
            {{ ref("base_people__staff_roster") }} as sr2
            on sr.report_to_employee_number = sr2.employee_number
        left join
            {{ ref("stg_people__campus_crosswalk") }} as cc
            on sr.home_work_location_name = cc.location_name
        left join
            {{ ref("int_people__leadership_crosswalk") }} as lc
            on sr.home_work_location_name = lc.home_work_location_name
        left join mdo on sr.business_unit_home_name = mdo.region
        left join
            ktaf_approvers as k on sr.department_home_name = k.department_home_name
        where
            sr.worker_termination_date is null
            or sr.worker_termination_date >= '2024-07-01'
    ),

    /* assigning approvers based on approval route*/
    approver_assignments as (
        select
            r.employee_number,
            r.payroll_group_code,
            r.worker_id,
            r.payroll_file_number,
            r.position_id,
            r.job_title,
            r.home_work_location_name,
            r.department_home_name,
            r.preferred_name_lastfirst,
            r.user_principal_name,
            r.google_email,
            r.assignment_status,
            r.business_unit_home_name,
            r.business_unit_home_code,
            r.worker_termination_date,
            r.route,
            r.campus,
            r.manager_employee_number,
            r.grandmanager_employee_number,
            r.dso_employee_number,
            r.sl_employee_number,
            r.head_of_school_employee_number,
            r.mdso_employee_number,
            r.mdo_employee_number,
            r.ktaf_approver,
            case
                /* School-based non-operations teammate*/
                when r.route = 'School' and r.department_home_name <> 'Operations'
                then r.sl_employee_number
                /* School-based operations teammate*/
                when r.route = 'School' and r.department_home_name = 'Operations'
                then
                    coalesce(
                        r.dso_employee_number,
                        r.mdso_employee_number,
                        r.mdo_employee_number
                    )
                /* Non-KTAF teammate with KTAF manager*/
                when r.route = 'MDSO'
                then r.mdso_employee_number
                /* Non-KTAF teammate with non-school location*/
                when r.route = 'MDO'
                then r.mdo_employee_number
                /* KTAF teammate (assigned according to submitter in app)*/
                when r.route = 'KTAF'
                then r.ktaf_approver
            end as first_approver_employee_number,
            case
                /* School-based non-operations teammate*/
                when r.route = 'School' and r.department_home_name <> 'Operations'
                then r.head_of_school_employee_number
                /* School-based operations teammate*/
                when r.route = 'School' and r.department_home_name = 'Operations'
                then coalesce(r.mdso_employee_number, r.mdo_employee_number)
                /* Non-KTAF teammate with KTAF manager*/
                when r.route = 'MDSO'
                then r.mdso_employee_number
                /* Non-KTAF teammate with non-school location*/
                when r.route = 'MDO'
                then r.mdo_employee_number
                /* KTAF teammate (assigned according to submitter in app)*/
                when r.route = 'KTAF'
                then r.ktaf_approver
            end as second_approver_employee_number,
        from route_assignments as r

    )
    
/* roster that feeds into Stipend and Bonus AppSheet*/
select
    r.employee_number,
    r.payroll_group_code,
    r.worker_id,
    r.payroll_file_number,
    r.position_id,
    r.job_title,
    r.home_work_location_name,
    r.department_home_name,
    r.preferred_name_lastfirst,
    r.user_principal_name,
    r.google_email,
    r.assignment_status,
    r.business_unit_home_name,
    r.business_unit_home_code,
    r.worker_termination_date,
    r.route,
    r.campus,
    r.dso_employee_number,
    r.sl_employee_number,
    r.head_of_school_employee_number,
    r.mdso_employee_number,
    r.mdo_employee_number,
    r.ktaf_approver,
    r.manager_employee_number,
    r.grandmanager_employee_number,
    case
        when r.first_approver_employee_number = r.employee_number
        then r.manager_employee_number
        when r.first_approver_employee_number is null and r.route <> 'MDSO'
        then r.manager_employee_number

        else r.first_approver_employee_number
    end as first_approver_employee_number,
    case
        when r.second_approver_employee_number = r.employee_number
        then r.grandmanager_employee_number
        when r.second_approver_employee_number is null and r.route <> 'MDSO'
        then r.grandmanager_employee_number
        else r.second_approver_employee_number
    end as second_approver_employee_number,
from approver_assignments as r
