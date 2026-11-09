-- depends_on: {{ ref("stg_kippadb__enrollment") }}
select id, student__c, status__c, actual_end_date__c,
from {{ source("kippadb", "enrollment") }}
where
    not isdeleted
    and status__c = 'Graduated'
    and actual_end_date__c > current_date('{{ var("local_timezone") }}')
