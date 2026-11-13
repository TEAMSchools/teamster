-- depends_on: {{ ref("stg_kippadb__standardized_test") }}
with
    ranked as (
        select
            id,
            contact__c,
            test_type__c,
            date__c,
            subject__c,

            row_number() over (
                partition by contact__c, test_type__c, date__c, subject__c
                order by lastmodifieddate desc, id desc
            ) as rn,
        from {{ source("kippadb", "standardized_test") }}
        where not isdeleted
    )

select id, contact__c, test_type__c, date__c, subject__c,
from ranked
where rn > 1
