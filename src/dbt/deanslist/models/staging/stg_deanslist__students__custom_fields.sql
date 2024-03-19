select
    s._dagster_partition_key as school_id,
    s.studentid as student_id,
    s.studentschoolid as student_school_id,

    cf.numvalue as num_value,

    nullif(cf.fieldcategory, '') as field_category,
    nullif(cf.fieldkey, '') as field_key,
    nullif(cf.fieldname, '') as field_name,
    nullif(cf.fieldtype, '') as field_type,
    nullif(cf.inputhtml, '') as input_html,
    nullif(cf.inputname, '') as input_name,
    nullif(cf.labelhtml, '') as label_html,
    nullif(cf.options, '') as `options`,
    nullif(cf.sourcetype, '') as source_type,
    nullif(cf.stringvalue, '') as string_value,
    nullif(cf.value, '') as `value`,

    safe_cast(nullif(cf.customfieldid, '') as int) as custom_field_id,
    safe_cast(nullif(cf.sourceid, '') as int) as source_id,
    safe_cast(nullif(cf.minuserlevel, '') as int) as min_user_level,

    if(nullif(cf.isfrontend, '') = 'Y', true, false) as is_front_end,
    if(nullif(cf.isrequired, '') = 'Y', true, false) as is_required,
from {{ source("deanslist", "src_deanslist__students") }} as s
cross join unnest(s.customfields) as cf
