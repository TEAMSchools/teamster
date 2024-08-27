select
    w.associate_oid,
    w.effective_date_start,
    w.effective_date_end,
    w.effective_date_timestamp,
    w.is_current_record,
    w.worker_id__id_value,
    w.worker_dates__original_hire_date,
    w.worker_dates__rehire_date,
    w.worker_dates__termination_date,
    w.person__family_name_1,
    w.person__given_name,
    w.person__legal_name__family_name_1,
    w.person__legal_name__given_name,
    w.person__birth_date,
    w.person__race_code_name,
    w.person__ethnicity_code_name,
    w.person__gender_code_name,
    w.race_ethnicity_reporting,
    w.is_prestart,

    wa.position_id,
    wa.job_title,
    wa.primary_indicator,
    wa.management_position_indicator,
    wa.assignment_status__status_code__name,
    wa.home_work_location__name_code__name,
    wa.worker_type_code__name,
    wa.wage_law_coverage__wage_law_name_code__name,
    wa.wage_law_coverage__coverage_code__name,
    wa.base_remuneration__annual_rate_amount__amount_value,

    ou.organizational_unit__assigned__business_unit__name,
    ou.organizational_unit__assigned__department__name,
    ou.organizational_unit__home__business_unit__name,
    ou.organizational_unit__home__department__name,

    rt.reports_to_worker_id__id_value,

    cf.wf_mgr_accrual_profile,
    cf.wf_mgr_badge_number,
    cf.wf_mgr_ee_type,
    cf.wf_mgr_pay_rule,

    w.person__family_name_1 || ', ' || w.person__given_name as person__formatted_name,
from {{ ref("stg_adp_workforce_now__workers") }} as w
inner join
    {{ ref("stg_adp_workforce_now__workers__work_assignments") }} as wa
    on w.associate_oid = wa.associate_oid
    and wa.effective_date_start between w.effective_date_start and w.effective_date_end
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
    {{ ref("int_adp_workforce_now__workers__custom_fields__pivot") }} as cf
    on w.associate_oid = cf.associate_oid
