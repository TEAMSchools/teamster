with
    kipp_aid as (
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
            coalesce(
                regexp_contains(notes__c, r'\[MAHER_FUND\|[^\]]*\]'), false
            ) as is_maher,
            regexp_extract(
                notes__c, r'\[MAHER_FUND\|[^\]]*?type=([A-Za-z]+)'
            ) as fund_type_tagged,
            regexp_extract(
                notes__c, r'\[MAHER_FUND\|[^\]]*?doc=([^\|\]]*)'
            ) as doc_type,
            trim(
                regexp_replace(notes__c, r'\s*\[MAHER_FUND\|[^\]]*\]\s*', '')
            ) as notes_clean,

            {{
                date_to_fiscal_year(
                    date_field="date__c", start_month=7, year_source="start"
                )
            }} as academic_year,
        from {{ source("kippadb", "kipp_aid") }}
        where not isdeleted
    )

select
    id,
    `name`,
    created_by_id,
    created_date,
    last_activity_date,
    last_modified_by_id,
    last_modified_date,
    system_modstamp,
    amount,
    `date`,
    kipp_aid_count,
    notes,
    status,
    student,
    `type`,
    is_maher,
    doc_type,
    notes_clean,
    academic_year,

    /* a tag with a misspelled or missing type falls back to Unclassified */
    case
        when not is_maher
        then null
        when fund_type_tagged in ('Emergency', 'Enrichment')
        then fund_type_tagged
        else 'Unclassified'
    end as fund_type,
from kipp_aid
