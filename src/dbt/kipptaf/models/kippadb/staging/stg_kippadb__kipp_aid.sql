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

    /* parsed from the appended [MAHER_FUND|v1|type=...|doc=...] marker tag */
    coalesce(regexp_contains(notes__c, r'\[MAHER_FUND\|[^\]]*\]'), false) as is_maher,
    regexp_extract(notes__c, r'\[MAHER_FUND\|[^\]]*?type=([A-Za-z]+)') as fund_type,
    regexp_extract(notes__c, r'\[MAHER_FUND\|[^\]]*?doc=([^\|\]]*)') as doc_type,
    trim(regexp_replace(notes__c, r'\s*\[MAHER_FUND\|[^\]]*\]\s*', '')) as notes_clean,

    {{ date_to_fiscal_year(date_field="date__c", start_month=7, year_source="start") }}
    as academic_year,

from {{ source("kippadb", "kipp_aid") }}
where not isdeleted
