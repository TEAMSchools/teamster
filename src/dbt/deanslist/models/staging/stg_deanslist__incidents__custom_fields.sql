select
    i.incident_id,

    safe_cast(nullif(cf.customfieldid, '') as int) as `custom_field_id`,
    safe_cast(nullif(cf.sourceid, '') as int) as `source_id`,
    safe_cast(nullif(cf.minuserlevel, '') as int) as `min_user_level`,

    nullif(cf.fieldcategory, '') as `field_category`,
    nullif(cf.fieldkey, '') as `field_key`,
    nullif(cf.fieldname, '') as `field_name`,
    nullif(cf.fieldtype, '') as `field_type`,
    nullif(cf.inputname, '') as `input_name`,
    nullif(cf.sourcetype, '') as `source_type`,
    nullif(cf.labelhtml, '') as `label_html`,
    nullif(cf.inputhtml, '') as `input_html`,
    nullif(cf.options, '') as `options`,

    nullif(cf.value, '') as `value`,
    nullif(cf.stringvalue, '') as `string_value`,
    cf.numvalue as `num_value`,

    if(nullif(cf.isfrontend, '') = 'Y', true, false) as `is_front_end`,
    if(nullif(cf.isrequired, '') = 'Y', true, false) as `is_required`,

    cf.selectedoptions as `selected_options`,
from {{ ref("stg_deanslist__incidents") }} as i
cross join unnest(i.custom_fields) as cf
