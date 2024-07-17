select
    wa.associate_oid,
    wa.item_id,
    wa.effective_date_start,
    wa.effective_date_end,
    wa.effective_date_timestamp,
    wa.is_current_record,

    rt.associateoid as reports_to_associate_oid,
    rt.positionid as reports_to_position_id,

    rt.workerid.idvalue as reports_to_worker_id__id_value,

    rt.workerid.schemecode.codevalue as reports_to_worker_id__scheme_code__code_value,
    rt.workerid.schemecode.longname as reports_to_worker_id__scheme_code__long_name,
    rt.workerid.schemecode.shortname as reports_to_worker_id__scheme_code__short_name,

    rt.reportstoworkername.formattedname as reports_to_worker_name__formatted_name,
    rt.reportstoworkername.givenname as reports_to_worker_name__given_name,
    rt.reportstoworkername.middlename as reports_to_worker_name__middle_name,
    rt.reportstoworkername.familyname1 as reports_to_worker_name__family_name1,
    rt.reportstoworkername.nickname as reports_to_worker_name__nick_name,

    rt.reportstoworkername.generationaffixcode.codevalue
    as reports_to_worker_name__generation_affix_code__code_value,
    rt.reportstoworkername.generationaffixcode.longname
    as reports_to_worker_name__generation_affix_code__long_name,
    rt.reportstoworkername.generationaffixcode.shortname
    as reports_to_worker_name__generation_affix_code__short_name,

    rt.reportstoworkername.qualificationaffixcode.codevalue
    as reports_to_worker_name__qualification_affix_code__code_value,
    rt.reportstoworkername.qualificationaffixcode.longname
    as reports_to_worker_name__qualification_affix_code__long_name,
    rt.reportstoworkername.qualificationaffixcode.shortname
    as reports_to_worker_name__qualification_affix_code__short_name,

    /* repeated records */
    rt.reportstoworkername.preferredsalutations
    as reports_to_worker_name__preferred_salutations,

    date(
        rt.workerid.schemecode.effectivedate
    ) as reports_to_worker_id__scheme_code__effective_date,

    date(
        rt.reportstoworkername.generationaffixcode.effectivedate
    ) as reports_to_worker_name__generation_affix_code__effective_date,
    date(
        rt.reportstoworkername.qualificationaffixcode.effectivedate
    ) as reports_to_worker_name__qualification_affix_code__effective_date,
from {{ ref("stg_adp_workforce_now__workers__work_assignments") }} as wa
cross join unnest(wa.reports_to) as rt
