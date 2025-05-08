select
    w.associate_oid,
    w.effective_date_start,
    w.effective_date_end,
    w.effective_date_start_timestamp,
    w.effective_date_end_timestamp,
    w.worker_id__id_value,
    w.worker_status__status_code__code_value,
    w.worker_dates__original_hire_date,
    w.worker_dates__rehire_date,
    w.worker_dates__termination_date,
    w.is_current_record,
    w.is_prestart,
    w.person__birth_date,
    w.person__ethnicity_code_name,
    w.person__family_name_1,
    w.person__gender_code_name,
    w.person__given_name,
    w.person__legal_address__city_name,
    w.person__legal_address__country_subdivision_level_1__code_value,
    w.person__legal_address__line_one,
    w.person__legal_address__postal_code,
    w.person__legal_name__family_name_1,
    w.person__legal_name__formatted_name,
    w.person__legal_name__given_name,
    w.person__race_code_name,
    w.race_ethnicity_reporting,
    w.worker_hire_date_recent,

    wa.item_id,
    wa.position_id,
    wa.job_title,
    wa.actual_start_date as work_assignment__actual_start_date,
    wa.termination_date as work_assignment__termination_date,
    wa.assignment_status__effective_date,
    wa.assignment_status__reason_code__name,
    wa.assignment_status__status_code__name,
    wa.base_remuneration__annual_rate_amount__amount_value,
    wa.base_remuneration__hourly_rate_amount__amount_value,
    wa.home_work_location__name_code__name,
    wa.management_position_indicator,
    wa.payroll_file_number,
    wa.payroll_group_code,
    wa.primary_indicator,
    wa.wage_law_coverage__coverage_code__name,
    wa.wage_law_coverage__wage_law_name_code__name,
    wa.worker_type_code__name,
    wa.additional_remunerations__rate__amount_value__sum,
    wa.benefits_eligibility_class__group_code__name,

    com.communication__personal_cell__formatted_number,
    com.communication__personal_email__email_uri,
    com.communication__work_cell__formatted_number,
    com.communication__work_email__email_uri,

    cf.employee_number as custom_field__employee_number,
    cf.life_experience_in_communities_we_serve,
    cf.miami_aces_number,
    cf.nj_pension_number,
    cf.preferred_race_ethnicity,
    cf.professional_experience_in_communities_we_serve,
    cf.received_sign_on_bonus,
    cf.remote_work_status,
    cf.teacher_prep_program,
    cf.wf_mgr_accrual_profile,
    cf.wf_mgr_badge_number,
    cf.wf_mgr_ee_type,
    cf.wf_mgr_home_hyperfind,
    cf.wf_mgr_loa_return_date,
    cf.wf_mgr_loa,
    cf.wf_mgr_pay_rule,
    cf.wf_mgr_trigger,

    ou.organizational_unit__assigned__business_unit__code_value,
    ou.organizational_unit__assigned__business_unit__name,
    ou.organizational_unit__assigned__department__name,
    ou.organizational_unit__home__business_unit__code_value,
    ou.organizational_unit__home__business_unit__name,
    ou.organizational_unit__home__department__name,

    rt.reports_to_worker_id__id_value,

    w.person__family_name_1 || ', ' || w.person__given_name as person__formatted_name,

    rtw.person__family_name_1
    || ', '
    || rtw.person__given_name as reports_to_formatted_name,

    {{
        dbt_utils.generate_surrogate_key(
            field_list=[
                "wa.assignment_status__status_code__name",
                "wa.base_remuneration__annual_rate_amount__amount_value",
                "wa.home_work_location__name_code__name",
                "wa.job_title",
                "ou.organizational_unit__assigned__business_unit__name",
                "ou.organizational_unit__assigned__department__name",
                "rt.reports_to_worker_id__id_value",
                "wa.wage_law_coverage__coverage_code__name",
                "cf.wf_mgr_accrual_profile",
                "cf.wf_mgr_badge_number",
                "cf.wf_mgr_ee_type",
                "cf.wf_mgr_pay_rule",
            ]
        )
    }} as wf_mgr_trigger_new,

    lag(wa.assignment_status__status_code__name, 1) over (
        partition by w.associate_oid order by wa.assignment_status__effective_date asc
    ) as assignment_status__status_code__name__lag,
from {{ ref("stg_adp_workforce_now__workers") }} as w
inner join
    {{ ref("stg_adp_workforce_now__workers__work_assignments") }} as wa
    on w.associate_oid = wa.associate_oid
    and wa.effective_date_start between w.effective_date_start and w.effective_date_end
left join
    {{ ref("int_adp_workforce_now__workers__communication__pivot") }} as com
    on w.associate_oid = com.associate_oid
left join
    {{ ref("int_adp_workforce_now__workers__custom_fields__pivot") }} as cf
    on w.associate_oid = cf.associate_oid
left join
    {{
        ref(
            "int_adp_workforce_now__workers__work_assignments__organizational_units__pivot"
        )
    }}
    as ou
    on wa.associate_oid = ou.associate_oid
    and wa.item_id = ou.item_id
    and ou.effective_date_start
    between wa.effective_date_start and wa.effective_date_end
left join
    {{ ref("stg_adp_workforce_now__workers__work_assignments__reports_to") }} as rt
    on wa.associate_oid = rt.associate_oid
    and wa.item_id = rt.item_id
    and rt.effective_date_start
    between wa.effective_date_start and wa.effective_date_end
left join
    {{ ref("stg_adp_workforce_now__workers") }} as rtw
    on rt.reports_to_associate_oid = rtw.associate_oid
    and rt.effective_date_start
    between rtw.effective_date_start and rtw.effective_date_end
