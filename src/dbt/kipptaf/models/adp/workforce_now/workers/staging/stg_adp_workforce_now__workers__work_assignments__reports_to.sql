with
    -- trunk-ignore(sqlfluff/ST03)
    reports_to as (
        select
            wa.associate_oid,
            wa.item_id,
            wa.effective_date_start,
            wa.effective_date_timestamp,

            rt.associateoid as reports_to_associate_oid,
            rt.positionid as reports_to_position_id,

            rt.workerid.idvalue as reports_to_worker_id__id_value,

            rt.workerid.schemecode.effectivedate
            as reports_to_worker_id__scheme_code__effective_date,
            rt.workerid.schemecode.codevalue
            as reports_to_worker_id__scheme_code__code_value,
            rt.workerid.schemecode.longname
            as reports_to_worker_id__scheme_code__long_name,
            rt.workerid.schemecode.shortname
            as reports_to_worker_id__scheme_code__short_name,

            rt.reportstoworkername.formattedname
            as reports_to_worker_name__formatted_name,
            rt.reportstoworkername.givenname as reports_to_worker_name__given_name,
            rt.reportstoworkername.middlename as reports_to_worker_name__middle_name,
            rt.reportstoworkername.familyname1 as reports_to_worker_name__family_name1,
            rt.reportstoworkername.nickname as reports_to_worker_name__nick_name,

            rt.reportstoworkername.generationaffixcode.effectivedate
            as reports_to_worker_name__generation_affix_code__effective_date,
            rt.reportstoworkername.generationaffixcode.codevalue
            as reports_to_worker_name__generation_affix_code__code_value,
            rt.reportstoworkername.generationaffixcode.longname
            as reports_to_worker_name__generation_affix_code__long_name,
            rt.reportstoworkername.generationaffixcode.shortname
            as reports_to_worker_name__generation_affix_code__short_name,

            rt.reportstoworkername.qualificationaffixcode.effectivedate
            as reports_to_worker_name__qualification_affix_code__effective_date,
            rt.reportstoworkername.qualificationaffixcode.codevalue
            as reports_to_worker_name__qualification_affix_code__code_value,
            rt.reportstoworkername.qualificationaffixcode.longname
            as reports_to_worker_name__qualification_affix_code__long_name,
            rt.reportstoworkername.qualificationaffixcode.shortname
            as reports_to_worker_name__qualification_affix_code__short_name,

            /* repeated records */
            rt.reportstoworkername.preferredsalutations
            as reports_to_worker_name__preferred_salutations,

            {{ dbt_utils.generate_surrogate_key(["to_json_string(rt)"]) }}
            as surrogate_key,
        from {{ ref("stg_adp_workforce_now__workers__work_assignments") }} as wa
        cross join unnest(wa.reports_to) as rt
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="reports_to",
                partition_by="associate_oid, item_id, surrogate_key",
                order_by="effective_date_timestamp asc",
            )
        }}
    ),

    with_end_date as (
        -- trunk-ignore(sqlfluff/AM04)
        select
            *,

            coalesce(
                date_sub(
                    lead(effective_date_start, 1) over (
                        partition by associate_oid, item_id
                        order by effective_date_start asc
                    ),
                    interval 1 day
                ),
                '9999-12-31'
            ) as effective_date_end,
        from deduplicate
    )

select
    *,

    if(
        current_date('{{ var("local_timezone") }}')
        between effective_date_start and effective_date_end,
        true,
        false
    ) as is_current_record,
from with_end_date
