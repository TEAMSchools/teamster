select
    wa.associate_oid,
    wa.item_id,
    wa.effective_date_start,
    wa.effective_date_timestamp,

    hou.typecode.effectivedate as type_code__effective_date,
    hou.typecode.codevalue as type_code__code_value,
    hou.typecode.longname as type_code__long_name,
    hou.typecode.shortname as type_code__short_name,

    hou.namecode.effectivedate as name_code__effective_date,
    hou.namecode.codevalue as name_code__code_value,
    hou.namecode.longname as name_code__long_name,
    hou.namecode.shortname as name_code__short_name,
from {{ ref("stg_adp_workforce_now__workers__work_assignments") }} as wa
cross join unnest(wa.home_organizational_units) as hou
