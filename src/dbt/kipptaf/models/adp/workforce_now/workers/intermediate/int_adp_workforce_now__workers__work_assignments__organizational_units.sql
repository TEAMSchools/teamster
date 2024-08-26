select
    wa.associate_oid,
    wa.item_id,
    wa.effective_date_start,
    wa.effective_date_end,
    wa.effective_date_timestamp,
    wa.is_current_record,

    ou.typecode.codevalue as type_code__code_value,
    ou.typecode.longname as type_code__long_name,
    ou.typecode.shortname as type_code__short_name,

    ou.namecode.codevalue as name_code__code_value,
    ou.namecode.longname as name_code__long_name,
    ou.namecode.shortname as name_code__short_name,

    date(ou.typecode.effectivedate) as type_code__effective_date,
    date(ou.namecode.effectivedate) as name_code__effective_date,

    'home' as organizational_unit_type,
from {{ ref("stg_adp_workforce_now__workers__work_assignments") }} as wa
cross join unnest(wa.home_organizational_units) as ou

union all

select
    wa.associate_oid,
    wa.item_id,
    wa.effective_date_start,
    wa.effective_date_end,
    wa.effective_date_timestamp,
    wa.is_current_record,

    ou.typecode.codevalue as type_code__code_value,
    ou.typecode.longname as type_code__long_name,
    ou.typecode.shortname as type_code__short_name,

    ou.namecode.codevalue as name_code__code_value,
    ou.namecode.longname as name_code__long_name,
    ou.namecode.shortname as name_code__short_name,

    date(ou.typecode.effectivedate) as type_code__effective_date,
    date(ou.namecode.effectivedate) as name_code__effective_date,

    'assigned' as organizational_unit_type,
from {{ ref("stg_adp_workforce_now__workers__work_assignments") }} as wa
cross join unnest(wa.assigned_organizational_units) as ou
