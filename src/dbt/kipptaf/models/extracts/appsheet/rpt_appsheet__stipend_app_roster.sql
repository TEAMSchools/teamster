with
    mdo as (
        select
            
            lc.region,
            max(
                if(sr.job_title = 'Managing Director of Operations', sr.employee_number, null)
            ) as mdo_employee_number,
        from {{ ref("base_people__staff_roster") }} as sr
        left join
            {{ ref("stg_people__location_crosswalk") }} as lc
            on sr.home_work_location_name = lc.name
        where sr.assignment_status = 'Active'
        group by lc.region
    ),

    roster as (
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

            coalesce(
                sr.home_work_location_abbreviation, sr.home_work_location_name
            ) as location_abbr,
            /* Route assignment determines approvers in app */
            case

                /* KTAF teammate with KTAF manager*/
                when
                    sr.business_unit_home_code = 'KIPP_TAF'
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
                else 'No Route'
            end as route,
            coalesce(cc.name, sr.home_work_location_name) as campus,
        from {{ ref("base_people__staff_roster") }} as sr
        left join
            {{ ref("base_people__staff_roster") }} as sr2
            on sr.report_to_employee_number = sr2.employee_number
        left join
            {{ ref("base_people__staff_roster") }} as sr3
            on sr2.report_to_employee_number = sr3.employee_number
        left join
            {{ ref("stg_people__campus_crosswalk") }} as cc
            on sr.home_work_location_name = cc.location_name
        left join
            {{ ref("int_people__leadership_crosswalk") }} as lc
            on sr.home_work_location_name = lc.home_work_location_name
        left join mdo on sr.business_unit_home_name = mdo.region
        where
            sr.worker_termination_date is null
            or sr.worker_termination_date >= '{{ var("current_academic_year") }}-07-01'
    )

select
    *,
    case
        /* School-based non-operations teammate*/
        when route = 'School' and department_home_name <> 'Operations'
        then sl_employee_number
        /* School-based operations teammate*/
        when route = 'School' and department_home_name = 'Operations'
        then dso_employee_number
        /* Non-KTAF teammate with KTAF manager*/
        when route = 'MDSO'
        then mdso_employee_number
        /* Non-KTAF teammate with non-school location*/
        when route = 'MDO'
        then mdo_employee_number
        /* KTAF teammate (assigned according to submitter in app)*/
        when route = 'KTAF'
        then null
        /*Outliers (assigned according to submitter in app)*/
        when route = 'No Route'
        then null
    end as first_approver_employee_number,
    case
        /* School-based non-operations teammate*/
        when route = 'School' and department_home_name <> 'Operations'
        then head_of_school_employee_number
        /* School-based operations teammate*/
        when route = 'School' and department_home_name = 'Operations'
        then mdso_employee_number
        /* Non-KTAF teammate with KTAF manager*/
        when route = 'MDSO'
        then mdso_employee_number
        /* Non-KTAF teammate with non-school location*/
        when route = 'MDO'
        then mdo_employee_number
        /* KTAF teammate (assigned according to submitter in app)*/
        when route = 'KTAF'
        then null
        /*Outliers (assigned according to submitter in app)*/
        when route = 'No Route'
        then null
    end as second_approver,
from roster
