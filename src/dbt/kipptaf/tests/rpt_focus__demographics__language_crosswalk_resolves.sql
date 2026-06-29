select cca.lang_parent_ss,
from {{ ref("int_finalsite__contact_custom_attributes") }} as cca
left join
    {{ ref("stg_google_sheets__focus__language_code_crosswalk") }} as lcc
    on cca.lang_parent_ss = lcc.finalsite_language
where cca.lang_parent_ss is not null and lcc.finalsite_language is null
