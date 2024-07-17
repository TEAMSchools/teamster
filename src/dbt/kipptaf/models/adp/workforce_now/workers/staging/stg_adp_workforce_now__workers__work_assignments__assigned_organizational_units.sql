select
    wa.associate_oid,
    wa.item_id,
    wa.effective_date_start,
    wa.effective_date_end,
    wa.effective_date_timestamp,
    wa.is_current_record,

    aou.typecode.effectivedate as type_code__effective_date,
    aou.typecode.codevalue as type_code__code_value,
    aou.typecode.longname as type_code__long_name,
    aou.typecode.shortname as type_code__short_name,

    aou.namecode.effectivedate as name_code__effective_date,
    aou.namecode.codevalue as name_code__code_value,
    aou.namecode.longname as name_code__long_name,
    aou.namecode.shortname as name_code__short_name,
from {{ ref("stg_adp_workforce_now__workers__work_assignments") }} as wa
cross join unnest(wa.assigned_organizational_units) as aou
