select
    id,
    `name`,
    createdbyid as created_by_id,
    createddate as created_date,
    lastactivitydate as last_activity_date,
    lastmodifiedbyid as last_modified_by_id,
    lastmodifieddate as last_modified_date,
    systemmodstamp as system_modstamp,
    amount__c as amount,
    date__c as `date`,
    kipp_aid_count__c as kipp_aid_count,
    notes__c as notes,
    status__c as status,
    student__c as student,
    type__c as `type`,
from {{ source("kippadb", "kipp_aid") }}
where not isdeleted
