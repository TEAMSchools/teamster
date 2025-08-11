select
    id,
    `name`,
    birthdate,
    ownerid as owner_id,
    actual_hs_graduation_date__c as actual_hs_graduation_date,
    college_match_display_gpa__c as college_match_display_gpa,
    recordtypeid as record_type_id,

    safe_cast(kipp_hs_class__c as int) as kipp_hs_class,
    safe_cast(school_specific_id__c as int) as school_specific_id,
from {{ source("kippadb", "contact") }}
where not isdeleted
