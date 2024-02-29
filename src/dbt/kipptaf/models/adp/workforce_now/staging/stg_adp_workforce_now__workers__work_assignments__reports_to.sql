select
    w.associateoid as associate_oid,

    /* workAssignments */
    wa.itemid as item_id,

    /* workAssignments.reportsTo */
    rt.associateoid as reports_to__associate_oid,
    rt.positionid as reports_to__position_id,

    rt.reportstoworkername.formattedname
    as reports_to__reports_to_worker_name__formatted_name,

    rt.workerid.idvalue as reports_to__worker_id__id_value,
    rt.workerid.schemecode.codevalue as reports_to__worker_id__scheme_code__code_value,
    rt.workerid.schemecode.shortname as reports_to__worker_id__scheme_code__short_name,

    timestamp(
        w._dagster_partition_date, '{{ var("local_timezone")}}'
    ) as as_of_date_timestamp,

    {{ dbt_utils.generate_surrogate_key(["to_json_string(wa.reportsto)"]) }}
    as reports_to_surrogate_key,
from {{ source("adp_workforce_now", "src_adp_workforce_now__workers") }} as w
cross join unnest(w.workassignments) as wa
cross join unnest(wa.reportsto) as rt
