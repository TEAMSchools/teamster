with
    work_assignments_parsed as (
        select
            w.associate_oid,
            w.effective_date_start,
            w.effective_date_end,
            w.effective_date_start_timestamp,
            w.is_current_record,

            wa.itemid as item_id,
            wa.positionid as position_id,
            wa.jobtitle as job_title,
            wa.payrollfilenumber as payroll_file_number,
            wa.payrollgroupcode as payroll_group_code,
            wa.payrollschedulegroupid as payroll_schedule_group_id,
            wa.primaryindicator as primary_indicator,
            wa.managementpositionindicator as management_position_indicator,
            wa.voluntaryindicator as voluntary_indicator,
            wa.fulltimeequivalenceratio as full_time_equivalence_ratio,

            wa.assignmentstatus.statuscode.codevalue
            as assignment_status__status_code__code_value,
            wa.assignmentstatus.statuscode.longname
            as assignment_status__status_code__long_name,
            wa.assignmentstatus.statuscode.shortname
            as assignment_status__status_code__short_name,

            wa.assignmentstatus.reasoncode.codevalue
            as assignment_status__reason_code__code_value,
            wa.assignmentstatus.reasoncode.longname
            as assignment_status__reason_code__long_name,
            wa.assignmentstatus.reasoncode.shortname
            as assignment_status__reason_code__short_name,

            wa.payrollprocessingstatuscode.codevalue
            as payroll_processing_status_code__code_value,
            wa.payrollprocessingstatuscode.longname
            as payroll_processing_status_code__long_name,
            wa.payrollprocessingstatuscode.shortname
            as payroll_processing_status_code__short_name,

            wa.baseremuneration.annualrateamount.currencycode
            as base_remuneration__annual_rate_amount__currency_code,
            wa.baseremuneration.annualrateamount.namecode.codevalue
            as base_remuneration__annual_rate_amount__name_code__code_value,
            wa.baseremuneration.annualrateamount.namecode.longname
            as base_remuneration__annual_rate_amount__name_code__long_name,
            wa.baseremuneration.annualrateamount.namecode.shortname
            as base_remuneration__annual_rate_amount__name_code__short_name,

            wa.baseremuneration.payperiodrateamount.currencycode
            as base_remuneration__pay_period_rate_amount__currency_code,
            wa.baseremuneration.payperiodrateamount.namecode.codevalue
            as base_remuneration__pay_period_rate_amount__name_code__code_value,
            wa.baseremuneration.payperiodrateamount.namecode.longname
            as base_remuneration__pay_period_rate_amount__name_code__long_name,
            wa.baseremuneration.payperiodrateamount.namecode.shortname
            as base_remuneration__pay_period_rate_amount__name_code__short_name,

            wa.baseremuneration.hourlyrateamount.currencycode
            as base_remuneration__hourly_rate_amount__currency_code,
            wa.baseremuneration.hourlyrateamount.namecode.codevalue
            as base_remuneration__hourly_rate_amount__name_code__code_value,
            wa.baseremuneration.hourlyrateamount.namecode.longname
            as base_remuneration__hourly_rate_amount__name_code__long_name,
            wa.baseremuneration.hourlyrateamount.namecode.shortname
            as base_remuneration__hourly_rate_amount__name_code__short_name,

            wa.baseremuneration.dailyrateamount.currencycode
            as base_remuneration__daily_rate_amount__currency_code,
            wa.baseremuneration.dailyrateamount.namecode.codevalue
            as base_remuneration__daily_rate_amount__name_code__code_value,
            wa.baseremuneration.dailyrateamount.namecode.longname
            as base_remuneration__daily_rate_amount__name_code__long_name,
            wa.baseremuneration.dailyrateamount.namecode.shortname
            as base_remuneration__daily_rate_amount__name_code__short_name,

            wa.homeworklocation.namecode.codevalue
            as home_work_location__name_code__code_value,
            wa.homeworklocation.namecode.longname
            as home_work_location__name_code__long_name,
            wa.homeworklocation.namecode.shortname
            as home_work_location__name_code__short_name,

            wa.homeworklocation.address.itemid as home_work_location__address__item_id,
            wa.homeworklocation.address.lineone
            as home_work_location__address__line_one,
            wa.homeworklocation.address.linetwo
            as home_work_location__address__line_two,
            wa.homeworklocation.address.linethree
            as home_work_location__address__line_three,
            wa.homeworklocation.address.cityname
            as home_work_location__address__city_name,
            wa.homeworklocation.address.postalcode
            as home_work_location__address__postal_code,
            wa.homeworklocation.address.countrycode
            as home_work_location__address__country_code,
            wa.homeworklocation.address.countrysubdivisionlevel1.subdivisiontype as
            home_work_location__address__country_subdivision_level_1__subdivision_type,
            wa.homeworklocation.address.countrysubdivisionlevel1.codevalue
            as home_work_location__address__country_subdivision_level_1__code_value,
            wa.homeworklocation.address.countrysubdivisionlevel1.longname
            as home_work_location__address__country_subdivision_level_1__long_name,
            wa.homeworklocation.address.countrysubdivisionlevel1.shortname
            as home_work_location__address__country_subdivision_level_1__short_name,
            wa.homeworklocation.address.countrysubdivisionlevel2.subdivisiontype as
            home_work_location__address__country_subdivision_level_2__subdivision_type,
            wa.homeworklocation.address.countrysubdivisionlevel2.codevalue
            as home_work_location__address__country_subdivision_level_2__code_value,
            wa.homeworklocation.address.countrysubdivisionlevel2.longname
            as home_work_location__address__country_subdivision_level_2__long_name,
            wa.homeworklocation.address.countrysubdivisionlevel2.shortname
            as home_work_location__address__country_subdivision_level_2__short_name,
            wa.homeworklocation.address.namecode.codevalue
            as home_work_location__address__name_code__code_value,
            wa.homeworklocation.address.namecode.longname
            as home_work_location__address__name_code__long_name,
            wa.homeworklocation.address.namecode.shortname
            as home_work_location__address__name_code__short_name,
            wa.homeworklocation.address.typecode.codevalue
            as home_work_location__address__type_code__code_value,
            wa.homeworklocation.address.typecode.longname
            as home_work_location__address__type_code__long_name,
            wa.homeworklocation.address.typecode.shortname
            as home_work_location__address__type_code__short_name,

            wa.jobcode.codevalue as job_code__code_value,
            wa.jobcode.longname as job_code__long_name,
            wa.jobcode.shortname as job_code__short_name,

            wa.paycyclecode.codevalue as pay_cycle_code__code_value,
            wa.paycyclecode.longname as pay_cycle_code__long_name,
            wa.paycyclecode.shortname as pay_cycle_code__short_name,

            wa.standardpayperiodhours.hoursquantity
            as standard_pay_period_hours__hours_quantity,

            wa.standardhours.hoursquantity as standard_hours__hours_quantity,

            wa.standardhours.unitcode.codevalue
            as standard_hours__unit_code__code_value,
            wa.standardhours.unitcode.longname as standard_hours__unit_code__long_name,
            wa.standardhours.unitcode.shortname
            as standard_hours__unit_code__short_name,

            wa.wagelawcoverage.coveragecode.codevalue
            as wage_law_coverage__coverage_code__code_value,
            wa.wagelawcoverage.coveragecode.longname
            as wage_law_coverage__coverage_code__long_name,
            wa.wagelawcoverage.coveragecode.shortname
            as wage_law_coverage__coverage_code__short_name,

            wa.wagelawcoverage.wagelawnamecode.codevalue
            as wage_law_coverage__wage_law_name_code__code_value,
            wa.wagelawcoverage.wagelawnamecode.longname
            as wage_law_coverage__wage_law_name_code__long_name,
            wa.wagelawcoverage.wagelawnamecode.shortname
            as wage_law_coverage__wage_law_name_code__short_name,

            wa.workertimeprofile.badgeid as worker_time_profile__badge_id,
            wa.workertimeprofile.timeandattendanceindicator
            as worker_time_profile__time_and_attendance_indicator,
            wa.workertimeprofile.timezonecode as worker_time_profile__time_zone_code,

            wa.workertimeprofile.timeservicesupervisor.associateoid
            as worker_time_profile__time_service_supervisor__associate_oid,
            wa.workertimeprofile.timeservicesupervisor.positionid
            as worker_time_profile__time_service_supervisor__position_id,
            wa.workertimeprofile.timeservicesupervisor.workerid.idvalue
            as worker_time_profile__time_service_supervisor__worker_id__id_value,

            -- trunk-ignore-begin(sqlfluff/LT05)
            wa.workertimeprofile.timeservicesupervisor.reportstoworkername.formattedname
            as
            worker_time_profile__time_service_supervisor__reports_to_worker_name__formatted_name,
            wa.workertimeprofile.timeservicesupervisor.reportstoworkername.familyname1
            as
            worker_time_profile__time_service_supervisor__reports_to_worker_name__family_name1,
            wa.workertimeprofile.timeservicesupervisor.reportstoworkername.givenname as
            worker_time_profile__time_service_supervisor__reports_to_worker_name__given_name,
            wa.workertimeprofile.timeservicesupervisor.reportstoworkername.middlename as
            worker_time_profile__time_service_supervisor__reports_to_worker_name__middle_name,
            -- trunk-ignore-end(sqlfluff/LT05)
            wa.workertypecode.codevalue as worker_type_code__code_value,
            wa.workertypecode.longname as worker_type_code__long_name,
            wa.workertypecode.shortname as worker_type_code__short_name,

            /* repeated records */
            wa.additionalremunerations as additional_remunerations,
            wa.assignedorganizationalunits as assigned_organizational_units,
            wa.assignedworklocations as assigned_work_locations,
            wa.customfieldgroup.codefields as custom_field_group__code_fields,
            wa.customfieldgroup.datefields as custom_field_group__date_fields,
            wa.customfieldgroup.indicatorfields as custom_field_group__indicator_fields,
            wa.customfieldgroup.multicodefields
            as custom_field_group__multi_code_fields,
            wa.customfieldgroup.numberfields as custom_field_group__number_fields,
            wa.customfieldgroup.stringfields as custom_field_group__string_fields,
            wa.homeorganizationalunits as home_organizational_units,
            wa.occupationalclassifications as occupational_classifications,
            wa.reportsto as reports_to,
            wa.workergroups as worker_groups,

            /* transformations */
            date(wa.hiredate) as hire_date,
            date(wa.actualstartdate) as actual_start_date,
            date(wa.senioritydate) as seniority_date,
            date(wa.terminationdate) as termination_date,

            cast(
                wa.baseremuneration.annualrateamount.amountvalue as numeric
            ) as base_remuneration__annual_rate_amount__amount_value,

            cast(
                wa.baseremuneration.hourlyrateamount.amountvalue as numeric
            ) as base_remuneration__hourly_rate_amount__amount_value,

            cast(
                wa.baseremuneration.dailyrateamount.amountvalue as numeric
            ) as base_remuneration__daily_rate_amount__amount_value,

            cast(
                wa.baseremuneration.payperiodrateamount.amountvalue as numeric
            ) as base_remuneration__pay_period_rate_amount__amount_value,

            date(
                wa.assignmentstatus.effectivedate
            ) as assignment_status__effective_date,
            date(
                wa.assignmentstatus.statuscode.effectivedate
            ) as assignment_status__status_code__effective_date,
            date(
                wa.assignmentstatus.reasoncode.effectivedate
            ) as assignment_status__reason_code__effective_date,

            date(
                wa.payrollprocessingstatuscode.effectivedate
            ) as payroll_processing_status_code__effective_date,

            date(
                wa.baseremuneration.effectivedate
            ) as base_remuneration__effective_date,
            date(
                wa.baseremuneration.annualrateamount.namecode.effectivedate
            ) as base_remuneration__annual_rate_amount__name_code__effective_date,
            date(
                wa.baseremuneration.payperiodrateamount.namecode.effectivedate
            ) as base_remuneration__pay_period_rate_amount__name_code__effective_date,
            date(
                wa.baseremuneration.hourlyrateamount.namecode.effectivedate
            ) as base_remuneration__hourly_rate_amount__name_code__effective_date,
            date(
                wa.baseremuneration.dailyrateamount.namecode.effectivedate
            ) as base_remuneration__daily_rate_amount__name_code__effective_date,

            date(wa.homeworklocation.address.countrysubdivisionlevel1.effectivedate)
            as home_work_location__address__country_subdivision_level_1__effective_date,
            date(wa.homeworklocation.address.countrysubdivisionlevel2.effectivedate)
            as home_work_location__address__country_subdivision_level_2__effective_date,
            date(
                wa.homeworklocation.address.namecode.effectivedate
            ) as home_work_location__address__name_code__effective_date,
            date(
                wa.homeworklocation.address.typecode.effectivedate
            ) as home_work_location__address__type_code__effective_date,
            date(
                wa.homeworklocation.namecode.effectivedate
            ) as home_work_location__name_code__effective_date,

            date(wa.jobcode.effectivedate) as job_code__effective_date,

            date(wa.paycyclecode.effectivedate) as pay_cycle_code__effective_date,

            date(
                wa.standardhours.unitcode.effectivedate
            ) as standard_hours__unit_code__effective_date,

            date(
                wa.wagelawcoverage.coveragecode.effectivedate
            ) as wage_law_coverage__coverage_code__effective_date,
            date(
                wa.wagelawcoverage.wagelawnamecode.effectivedate
            ) as wage_law_coverage__wage_law_name_code__effective_date,

            date(wa.workertypecode.effectivedate) as worker_type_code__effective_date,

            {{ dbt_utils.generate_surrogate_key(["to_json_string(wa)"]) }}
            as surrogate_key,
        from {{ ref("stg_adp_workforce_now__workers") }} as w
        cross join unnest(w.work_assignments) as wa
    )

select
    *,

    (
        select sum(ar.rate.amountvalue), from unnest(additional_remunerations) as ar
    ) as additional_remunerations__rate__amount_value__sum,

    (
        select coalesce(wg.groupcode.longname, wg.groupcode.shortname),
        from unnest(worker_groups) as wg
        where wg.namecode.codevalue = 'Benefits Eligibility Class'
    ) as benefits_eligibility_class__group_code__name,

    coalesce(
        home_work_location__name_code__long_name,
        home_work_location__name_code__short_name
    ) as home_work_location__name_code__name,
    coalesce(
        worker_type_code__long_name, worker_type_code__short_name
    ) as worker_type_code__name,
    coalesce(
        assignment_status__status_code__long_name,
        assignment_status__status_code__short_name
    ) as assignment_status__status_code__name,
    coalesce(
        assignment_status__reason_code__long_name,
        assignment_status__reason_code__short_name
    ) as assignment_status__reason_code__name,
    coalesce(
        wage_law_coverage__coverage_code__long_name,
        wage_law_coverage__coverage_code__short_name
    ) as wage_law_coverage__coverage_code__name,
    coalesce(
        wage_law_coverage__wage_law_name_code__long_name,
        wage_law_coverage__wage_law_name_code__short_name
    ) as wage_law_coverage__wage_law_name_code__name,
from work_assignments_parsed
